#!/usr/bin/env python3
"""Batch-extract structured data from PDFs with LM Studio.

This script reads every PDF from an input directory, runs OCR on each page,
sends the extracted text plus a JSON schema to LM Studio's OpenAI-compatible
`/v1/chat/completions` endpoint, and writes one JSON output file per PDF.

Usage example:

    python lmstudio_pdf_batch_extract.py \
        --input-dir /path/to/pdfs \
        --output-dir /path/to/output \
        --schema-file /path/to/schema.json \
        --model qwen2.5-7b-instruct

Requirements:

    sudo apt install poppler-utils tesseract-ocr
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured JSON from PDFs with LM Studio."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing PDF files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where JSON outputs will be written.",
    )
    parser.add_argument(
        "--schema-file",
        required=True,
        type=Path,
        help="Path to a JSON Schema file.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="LM Studio model identifier loaded in the local server.",
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:1234/v1/chat/completions",
        help="LM Studio chat completions endpoint.",
    )
    parser.add_argument(
        "--system-prompt",
        default=(
            "Extract structured data from the provided PDF text. "
            "Return only JSON that matches the supplied schema. "
            "If a field is missing, use null when allowed by the schema."
        ),
        help="System instruction sent to the model.",
    )
    parser.add_argument(
        "--user-prompt",
        default="Extract structured data from this PDF text.",
        help="User instruction prefix sent before the extracted PDF text.",
    )
    parser.add_argument(
        "--glob",
        default="*.pdf",
        help="Glob pattern for PDF discovery inside the input directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JSON output files.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the model.",
    )
    return parser.parse_args()


def read_schema(schema_file: Path) -> dict[str, Any]:
    with schema_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_required_commands() -> None:
    missing = [
        command
        for command in ("pdftoppm", "tesseract")
        if shutil.which(command) is None
    ]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing required system commands: {joined}. Install poppler-utils and tesseract-ocr."
        )


def extract_pdf_text(pdf_path: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="lmstudio_pdf_ocr_") as temp_dir:
        temp_path = Path(temp_dir)
        image_prefix = temp_path / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                str(pdf_path),
                str(image_prefix),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        pages: list[str] = []
        image_files = sorted(temp_path.glob("page-*.png"))
        if not image_files:
            raise ValueError(f"No page images were generated for {pdf_path}")

        for index, image_file in enumerate(image_files, start=1):
            result = subprocess.run(
                ["tesseract", str(image_file), "stdout"],
                check=True,
                capture_output=True,
                text=True,
            )
            pages.append(f"\n--- OCR Page {index} ---\n{result.stdout.strip()}")

    return "\n".join(pages).strip()


def build_payload(
    model: str,
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    pdf_name: str,
    pdf_text: str,
    temperature: float,
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"{user_prompt}\n\n"
                    f"PDF filename: {pdf_name}\n\n"
                    "PDF text:\n"
                    f"{pdf_text}"
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "pdf_extraction",
                "schema": schema,
            },
        },
    }


def post_json(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def parse_model_json(response_data: dict[str, Any]) -> Any:
    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Unexpected LM Studio response shape: {response_data}"
        ) from exc

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        content = "\n".join(text_parts)

    if not isinstance(content, str):
        raise ValueError(f"Unexpected message content: {content!r}")

    return json.loads(content)


def iter_pdfs(input_dir: Path, pattern: str) -> list[Path]:
    return sorted(path for path in input_dir.glob(pattern) if path.is_file())


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    schema: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    output_file = output_dir / f"{pdf_path.stem}.json"
    if output_file.exists() and not args.overwrite:
        print(f"Skipping {pdf_path.name}: output already exists", file=sys.stderr)
        return

    pdf_text = extract_pdf_text(pdf_path)
    if not pdf_text:
        raise ValueError(f"No extractable text found in {pdf_path}")

    payload = build_payload(
        model=args.model,
        schema=schema,
        system_prompt=args.system_prompt,
        user_prompt=args.user_prompt,
        pdf_name=pdf_path.name,
        pdf_text=pdf_text,
        temperature=args.temperature,
    )
    response_data = post_json(args.endpoint, payload)
    extracted_json = parse_model_json(response_data)

    with output_file.open("w", encoding="utf-8") as handle:
        json.dump(extracted_json, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Saved {output_file}")


def main() -> int:
    args = parse_args()
    ensure_required_commands()

    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")
    if not args.schema_file.is_file():
        raise SystemExit(f"Schema file does not exist: {args.schema_file}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    schema = read_schema(args.schema_file)
    pdf_files = iter_pdfs(args.input_dir, args.glob)
    if not pdf_files:
        raise SystemExit(
            f"No PDF files matching {args.glob!r} found in {args.input_dir}"
        )

    failures = 0
    for pdf_path in pdf_files:
        try:
            process_pdf(pdf_path, args.output_dir, schema, args)
        except urllib.error.HTTPError as exc:
            failures += 1
            error_body = exc.read().decode("utf-8", errors="replace")
            print(
                f"HTTP error for {pdf_path.name}: {exc.code} {exc.reason}\n{error_body}",
                file=sys.stderr,
            )
        except Exception as exc:  # pragma: no cover - CLI error reporting
            failures += 1
            print(f"Failed to process {pdf_path.name}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.file_utils import traverse_job_folder


def test_traverse_job_folder_excludes_output_path(tmp_path):
    job_dir = tmp_path / "job"
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"
    source_docs_dir = output_dir / "source-documents"

    source_docs_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)

    original_pdf = input_dir / "A1.pdf"
    original_pdf.write_bytes(b"%PDF-1.4 original")

    archived_pdf = source_docs_dir / "A1.pdf"
    archived_pdf.write_bytes(b"%PDF-1.4 archived")

    # Without exclusions both files are discovered
    all_files = sorted(traverse_job_folder(str(job_dir)))
    assert len(all_files) == 2
    assert {Path(f).name for f in all_files} == {"A1.pdf"}

    # Excluding the output folder removes the duplicate archive
    unique_files = traverse_job_folder(str(job_dir), exclude_paths=[str(output_dir)])
    assert unique_files == [str(original_pdf.resolve())]

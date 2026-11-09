import asyncio
import tempfile

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app.storage.s3 import S3Storage


async def main() -> None:
    storage = S3Storage()

    content = b"AWS S3 integration test successful."

    key = f"_health-check/{uuid4()}.txt"

    # Upload
    await storage.upload_file(
        BytesIO(content),
        key=key,
        content_type="text/plain",
    )

    print("Upload successful.")

    # Download
    with tempfile.TemporaryDirectory() as temp_dir:
        destination = Path(temp_dir) / "test.txt"

        await storage.download_file(
            key=key,
            destination=destination,
        )

        downloaded_content = destination.read_bytes()

        assert downloaded_content == content

        print("Download successful.")

    # Delete
    await storage.delete_file(key=key)

    print("Delete successful.")
    print("All S3 tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
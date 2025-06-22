# Document Processing Feature

The expense tracking bot now supports automatic processing of receipts from various document formats, not just photos.

## Supported Formats

### Images
- **JPEG/JPG** - Standard photo format
- **PNG** - High-quality images with transparency
- **WebP** - Modern web image format
- **BMP** - Bitmap images

### Documents
- **PDF** - Portable Document Format (scanned receipts, digital receipts)
- **DOCX** - Microsoft Word documents containing receipt images
- **DOC** - Legacy Word format

## How It Works

1. **Send Document**: Users can send any supported document format to the bot
2. **Automatic Detection**: The bot automatically detects the file type
3. **Processing**:
   - **PDF**: Converts to image (first page or extracts embedded images)
   - **Word**: Extracts embedded images
   - **Images**: Direct processing
4. **OCR**: Uses the same OCR pipeline (Tesseract/OpenAI Vision)
5. **Auto-categorization**: Detects expense category based on merchant and items
6. **Auto-save**: Saves the expense with detected category

## Features

### Smart Category Detection
The bot automatically detects categories based on:
- Merchant names (e.g., Magnum → Food, Yandex → Transport)
- Receipt content and items
- Common patterns in different languages

### Multi-page PDF Support
- Processes up to 5 pages to find receipt content
- Extracts embedded images from PDFs
- Falls back to text extraction if no images found

### File Size Limits
- Documents: Up to 20MB
- Images: Up to 10MB

### Metadata Storage
Each transaction stores:
- Source type (photo/document)
- Original filename
- Document type (MIME type)

## Usage Examples

### Sending a PDF Receipt
1. Download or save receipt as PDF
2. Send the PDF file to the bot
3. Bot processes and saves the expense automatically

### Sending a Photo as Document
1. Instead of sending as compressed photo, send as file
2. Better quality = better OCR accuracy
3. Supports multiple image formats

### Word Documents
1. Useful for receipts embedded in reports
2. Bot extracts images from the document
3. Processes the first receipt image found

## Technical Implementation

### New Components

1. **Document Handler** (`src/bot/handlers/document.py`)
   - Handles all document messages
   - Validates file types and sizes
   - Coordinates processing

2. **Document Processor** (`src/services/document_processor.py`)
   - PDF to image conversion
   - Image extraction from Word documents
   - Text to image fallback

3. **Enhanced OCR** (`src/services/ocr.py`)
   - Added category detection
   - Improved merchant recognition
   - Better multi-language support

### Dependencies

```bash
# PDF Processing
pypdf==5.1.0          # PDF manipulation
pdf2image==1.17.0     # PDF to image conversion
poppler-utils         # System dependency for pdf2image

# Document Processing
python-docx==1.1.2    # Word document processing
python-magic==0.4.27  # File type validation
```

### System Requirements

For full PDF support, install poppler:

**macOS**:
```bash
brew install poppler
```

**Ubuntu/Debian**:
```bash
sudo apt-get install poppler-utils
```

**Docker** (already included in Dockerfile):
```dockerfile
RUN apt-get install -y poppler-utils
```

## Localization

New messages added for both Russian and Kazakh:

### Russian
- `document.processing` - "Обрабатываю документ..."
- `document.unsupported_format` - Error for unsupported formats
- `document.file_too_large` - Error for large files
- `document.pdf_conversion_error` - PDF processing error
- `document.no_images_found` - No images in document
- `document.processing_error` - General processing error
- `document.from_file` - "Из файла"

### Kazakh
- Similar messages in Kazakh language

## Configuration

All document processing uses existing configuration:
- `ENABLE_OCR` - Must be True
- `MAX_IMAGE_SIZE_MB` - Applies to extracted images
- OCR settings (Tesseract/OpenAI Vision)

## Future Enhancements

1. **Multi-receipt Processing**
   - Process multiple receipts from one PDF
   - Batch import functionality

2. **Email Integration**
   - Forward receipt emails to bot
   - Process email attachments

3. **Cloud Storage**
   - Direct import from Google Drive/Dropbox
   - Backup processed receipts

4. **Advanced Formats**
   - Excel/CSV import for bulk expenses
   - Screenshot processing
   - E-receipt QR code scanning
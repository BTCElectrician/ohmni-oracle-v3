# Azure Function PDF Retrieval Verification Checklist

## Overview
When querying the `drawings_unified` Azure Search index, search results contain source file metadata that allows the Azure Function to retrieve the original PDF documents from Azure Blob Storage.

## ✅ Required Fields in Search Queries

### 1. Include Source Fields in `$select`
When querying Azure Search, ensure these fields are included in the `$select` parameter:

**Required for PDF retrieval:**
- `source_uri` - Full Azure Blob Storage URL (preferred method)
- `source_blob` - Blob path within container (fallback)
- `source_account` - Storage account name
- `source_container` - Container name
- `source_storage_name` - Alternative storage path

**Additional useful fields:**
- `sheet_number` - For identifying which sheet the result came from
- `doc_type` - To distinguish between sheet_chunk, schedule_row, template, etc.
- `id` - Document ID for tracking

**Example query:**
```json
{
  "search": "kitchen circuits",
  "select": "id,doc_type,sheet_number,source_uri,source_blob,source_account,source_container,source_storage_name,content",
  "top": 25
}
```

## ✅ Azure Storage Authentication

### 2. Storage Account Access
Verify the Azure Function has one of the following:

- [ ] **Connection String** - For direct blob access
- [ ] **SAS Token** - For time-limited access
- [ ] **Managed Identity** - For Azure-hosted functions (recommended)
- [ ] **Storage Account Key** - For service principal access

**Storage Account Details:**
- Account name: `aisearchohmniv1` (or check `source_account` field in results)
- Container: `drawings-unified` (or check `source_container` field in results)

### 3. SAS Token Generation (if needed)
If using SAS tokens, verify the Function can:
- [ ] Generate SAS tokens with `read` permission
- [ ] Set appropriate expiration (e.g., 1 hour for downloads)
- [ ] Append SAS token to `source_uri` when downloading

## ✅ PDF Download Implementation

### 4. Download Method Priority
Implement download logic with fallback:

**Primary method (if `source_uri` exists):**
```python
# Use source_uri directly (may need SAS token appended)
blob_url = result.get("source_uri")
if blob_url:
    # Append SAS token if needed
    download_url = f"{blob_url}?{sas_token}"
    # Download PDF
```

**Fallback method (if `source_uri` missing, use components):**
```python
# Construct from components
account = result.get("source_account")
container = result.get("source_container")
blob_path = result.get("source_blob")

if account and container and blob_path:
    # Use Azure Storage SDK
    blob_client = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=credential
    ).get_blob_client(container=container, blob=blob_path)
    # Download PDF
```

### 5. URL Encoding
- [ ] Handle URL-encoded blob paths (e.g., `%20` for spaces)
- [ ] Decode `source_blob` if constructing URLs manually
- [ ] Preserve special characters in blob names

## ✅ Error Handling

### 6. Missing Source Fields
Handle cases where source fields may be missing:

- [ ] Check if `source_uri` exists before using it
- [ ] Fall back to `source_blob` + `source_account` + `source_container` if `source_uri` missing
- [ ] Log warning if no source fields available
- [ ] Return appropriate error to client (404, 500, etc.)

### 7. Blob Not Found Errors
Handle Azure Storage errors:

- [ ] Catch `ResourceNotFoundError` (blob doesn't exist)
- [ ] Catch `AzureError` for network/auth issues
- [ ] Return 404 to client if blob not found
- [ ] Log errors for debugging

### 8. Partial Results
Handle documents without source files:

- [ ] Some documents may have `source_file: "<blob/path>.pdf"` (placeholder)
- [ ] Skip download if source fields are placeholders
- [ ] Consider returning metadata-only results

## ✅ Performance & Optimization

### 9. Caching Strategy
- [ ] Consider caching downloaded PDFs (if appropriate)
- [ ] Implement cache invalidation based on blob ETag (`source_pdf_etag` if available)
- [ ] Set appropriate cache headers for client-side caching

### 10. Streaming Downloads
- [ ] Stream PDF downloads (don't load entire file into memory)
- [ ] Use chunked downloads for large PDFs
- [ ] Set appropriate timeout values

### 11. Concurrent Downloads
- [ ] If downloading multiple PDFs, use async/parallel downloads
- [ ] Implement rate limiting to avoid overwhelming storage
- [ ] Consider batch operations if downloading many files

## ✅ Document Type Handling

### 12. Different Document Types
Handle different `doc_type` values:

- [ ] `sheet_chunk` - PDF source available
- [ ] `schedule_row` - PDF source available
- [ ] `template` - May have `source_pdf_blob_path` field (alternative)
- [ ] `sheet` - PDF source available

**Note:** All document types in `drawings_unified` index should have source fields, but verify behavior.

## ✅ Testing Checklist

### 13. Test Scenarios
Verify the following scenarios work:

- [ ] Download PDF using `source_uri` directly
- [ ] Download PDF using `source_blob` + account + container
- [ ] Handle URL-encoded blob names
- [ ] Handle missing source fields gracefully
- [ ] Handle blob not found errors
- [ ] Handle authentication failures
- [ ] Test with different document types (sheet_chunk, schedule_row, template)
- [ ] Test with multiple results (batch downloads)

### 14. Sample Test Data
Use these fields from actual search results:

```json
{
  "id": "ohmni-30J7925-E5-00-chunk-0001",
  "doc_type": "sheet_chunk",
  "sheet_number": "E5.00",
  "source_uri": "https://aisearchohmniv1.blob.core.windows.net/drawings-unified/sources/electrical/e5-00-panel-schedules-copy/E5.00-PANEL-SCHEDULES-Rev.3%20copy.pdf",
  "source_account": "aisearchohmniv1",
  "source_container": "drawings-unified",
  "source_blob": "sources/electrical/e5-00-panel-schedules-copy/E5.00-PANEL-SCHEDULES-Rev.3%20copy.pdf",
  "source_storage_name": "sources/electrical/e5-00-panel-schedules-copy/E5.00-PANEL-SCHEDULES-Rev.3 copy.pdf"
}
```

## ✅ Security Considerations

### 15. Access Control
- [ ] Verify Function has appropriate RBAC permissions on storage account
- [ ] Don't expose storage account keys in code/logs
- [ ] Use Managed Identity where possible
- [ ] Implement tenant/project filtering if multi-tenant

### 16. URL Validation
- [ ] Validate `source_uri` is from expected storage account
- [ ] Prevent SSRF attacks by validating URLs
- [ ] Sanitize blob paths before constructing URLs

## ✅ Monitoring & Logging

### 17. Logging Requirements
Log the following for debugging:

- [ ] Document ID when downloading PDF
- [ ] Source URI/blob path used
- [ ] Download success/failure
- [ ] Download duration
- [ ] File size downloaded
- [ ] Any errors encountered

### 18. Metrics to Track
Monitor:

- [ ] Number of PDF downloads per request
- [ ] Average download time
- [ ] Error rate (blob not found, auth failures, etc.)
- [ ] Cache hit rate (if caching implemented)

## ✅ Integration Points

### 19. API Response Format
Decide how to return PDFs to clients:

- [ ] Direct blob URL (with SAS token) - redirect client to download
- [ ] Proxy download - Function downloads and streams to client
- [ ] Metadata only - return source fields, let client download

### 20. Response Headers
If proxying downloads, set appropriate headers:

- [ ] `Content-Type: application/pdf`
- [ ] `Content-Disposition: attachment; filename="..."` (or inline for viewing)
- [ ] `Content-Length` (if known)
- [ ] Cache headers if appropriate

---

## Quick Reference: Source Fields Available

| Field | Type | Description | Usage |
|-------|------|-------------|-------|
| `source_uri` | String | Full Azure Blob Storage URL | Primary download method |
| `source_blob` | String | Blob path within container | Fallback construction |
| `source_account` | String | Storage account name | Fallback construction |
| `source_container` | String | Container name | Fallback construction |
| `source_storage_name` | String | Alternative storage path | Alternative fallback |
| `source_file` | String | Original filename (may be placeholder) | Display only |
| `source_pdf_etag` | String | Blob ETag (if available) | Cache validation |

---

## Questions for Azure Function Team

1. What authentication method will be used? (Managed Identity, SAS, Connection String)
2. Will PDFs be proxied through the Function or returned as direct blob URLs?
3. What's the expected file size range? (affects streaming strategy)
4. Is caching required? If so, what's the cache duration?
5. Are there any tenant/project-level access restrictions to implement?
6. What's the expected concurrent download volume?


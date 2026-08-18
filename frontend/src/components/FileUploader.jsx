import React, { useState, useRef } from 'react';
import { validateFile } from '../utils/validators';
import { formatFileSize } from '../utils/formatters';

export function FileUploader({
  title = 'Upload Document',
  description = 'Supports PDF or Word (.docx) documents up to 10MB',
  allowedExtensions = ['.pdf', '.docx'],
  maxSizeBytes = 10 * 1024 * 1024,
  onFileSelected,
  selectedFile,
  isLoading = false,
  error = null,
  successMessage = null,
}) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const inputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = (file) => {
    setValidationError(null);
    const result = validateFile(file, allowedExtensions, maxSizeBytes);
    if (!result.isValid) {
      setValidationError(result.message);
      if (onFileSelected) onFileSelected(null);
      return;
    }
    if (onFileSelected) {
      onFileSelected(file);
    }
  };

  const triggerSelect = () => {
    if (inputRef.current) {
      inputRef.current.click();
    }
  };

  const displayError = validationError || error;

  return (
    <div className="file-uploader-container">
      <label className="file-uploader-label">{title}</label>
      <div
        className={`file-dropzone ${isDragOver ? 'drag-over' : ''} ${selectedFile ? 'has-file' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={triggerSelect}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          style={{ display: 'none' }}
          onChange={handleChange}
          disabled={isLoading}
        />

        <div className="dropzone-icon">
          {selectedFile ? '📄' : '📁'}
        </div>

        {selectedFile ? (
          <div className="file-info-selected">
            <span className="file-name">{selectedFile.name}</span>
            <span className="file-size">({formatFileSize(selectedFile.size)})</span>
            <span className="file-change-hint">Click or drop to replace</span>
          </div>
        ) : (
          <div className="dropzone-text">
            <p className="dropzone-primary-text">
              <strong>Click to upload</strong> or drag and drop file here
            </p>
            <p className="dropzone-hint">{description}</p>
            <div className="file-format-tags">
              {allowedExtensions.map((ext) => (
                <span key={ext} className="format-tag">{ext.toUpperCase()}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {displayError && (
        <div className="upload-error-text">
          <span>⚠️ {displayError}</span>
        </div>
      )}

      {successMessage && (
        <div className="upload-success-text">
          <span>✅ {successMessage}</span>
        </div>
      )}
    </div>
  );
}

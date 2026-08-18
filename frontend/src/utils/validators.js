/**
 * Utility validation functions for forms and file uploads.
 */

export function isValidEmail(email) {
  if (!email || typeof email !== 'string') return false;
  const emailRegex = /^[\w.-]+@[\w.-]+\.\w+$/;
  return emailRegex.test(email.trim());
}

export function validatePassword(password) {
  if (!password || typeof password !== 'string') {
    return { isValid: false, message: 'Password is required' };
  }
  if (password.length < 6) {
    return { isValid: false, message: 'Password must be at least 6 characters long' };
  }
  return { isValid: true, message: '' };
}

export function validatePasswordMatch(password, confirmPassword) {
  if (password !== confirmPassword) {
    return { isValid: false, message: 'Passwords do not match' };
  }
  return { isValid: true, message: '' };
}

export function validateFile(file, allowedExtensions = ['.pdf', '.docx'], maxSizeBytes = 10 * 1024 * 1024) {
  if (!file) {
    return { isValid: false, message: 'No file selected.' };
  }

  const name = file.name || '';
  const ext = '.' + name.split('.').pop().toLowerCase();
  
  if (!allowedExtensions.includes(ext)) {
    return {
      isValid: false,
      message: `Invalid file format (${ext}). Only ${allowedExtensions.join(', ')} files are allowed.`
    };
  }

  if (file.size > maxSizeBytes) {
    const maxMb = maxSizeBytes / (1024 * 1024);
    return {
      isValid: false,
      message: `File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum size is ${maxMb} MB.`
    };
  }

  if (file.size === 0) {
    return { isValid: false, message: 'The selected file is empty (0 bytes).' };
  }

  return { isValid: true, message: '' };
}

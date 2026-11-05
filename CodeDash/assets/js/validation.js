"use strict";

((root, factory) => {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else root.CodeDashValidation = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  function validateLogin(email, password) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return "Enter a valid email address.";
    }
    if (!password) return "Enter your password.";
    return "";
  }
  function validateRegistration(username, email, password, confirm) {
    if (!/^[a-zA-Z0-9_-]{3,30}$/.test(username)) {
      return "Username must be 3–30 letters, numbers, underscores, or hyphens.";
    }
    const loginError = validateLogin(email, password);
    if (loginError) return loginError;
    if (password.length < 8) {
      return "Password must be at least 8 characters.";
    }
    if (password !== confirm) return "Passwords do not match.";
    return "";
  }
  return { validateLogin, validateRegistration };
});

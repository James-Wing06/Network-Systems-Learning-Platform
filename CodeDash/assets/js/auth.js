/* global CodeDashValidation */
"use strict";

const form = document.querySelector("#login-form, #register-form");
const message = document.querySelector("#form-message");
if (form && message) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = form.querySelector("#email").value.trim();
    const password = form.querySelector("#password").value;
    const isRegistration = form.id === "register-form";
    const error = isRegistration
      ? CodeDashValidation.validateRegistration(
          form.querySelector("#username").value.trim(),
          email,
          password,
          form.querySelector("#confirm").value,
        )
      : CodeDashValidation.validateLogin(email, password);
    message.className = `notice ${error ? "error" : ""}`;
    message.textContent =
      error ||
      "Form is valid. Account API is not connected; no account was created or authenticated.";
  });
}

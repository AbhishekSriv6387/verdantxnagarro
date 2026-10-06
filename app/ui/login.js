'use strict';
document.querySelector('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target, button = form.querySelector('button'), error = document.querySelector('#login-error');
  button.disabled = true; error.textContent = '';
  try {
    const response = await fetch('/api/auth/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your sign-in details.');
    location.assign('/');
  } catch (err) {error.textContent = err.message;}
  finally {button.disabled = false;}
});

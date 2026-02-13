# Secure Local Tunnel Setup (ngrok)

This guide provides a security-hardened approach to setting up ngrok. Following DevOps best practices, we avoid passing sensitive tokens directly in CLI commands to prevent them from being logged in shell history (`.bash_history` / `.zsh_history`).

---

## 1. Install & Secure Credential Storage

### Step 1: Install
```bash
brew install ngrok/ngrok/ngrok
```

### Step 2: Store Token in Environment
Never run `ngrok config add-authtoken <token>` directly, as it writes the token in plain text to your history. Instead, add it to your local environment file (`.env`) or your shell profile.

1. Open your `.env` file (ensure it is in `.gitignore`).
2. Add the token:
   ```bash
   # .env file
   NGROK_AUTHTOKEN=your_token_here_from_dashboard
   ```
3. Load it into your current session:
   ```bash
   export $(grep -v '^#' .env | xargs)
   ```

---

## 2. Execute via Environment Variable

To start the tunnel without exposing credentials in the configuration file or process list, use the environment variable directly:

```bash
ngrok http 8000 --authtoken $NGROK_AUTHTOKEN
```

### Advanced: Using ngrok Configuration Files
For a persistent and repeatable setup, use a `ngrok.yml` file, but **reference environment variables** to keep it clean.

1. Create a `ngrok.yml` in your project root (add this to `.gitignore`).
2. Define your tunnel:
   ```yaml
   authtoken: ${NGROK_AUTHTOKEN}
   tunnels:
     vyapaar-mcp:
       proto: http
       addr: 8000
       schemes:
         - https
   ```
3. Run using the config:
   ```bash
   ngrok start --config ngrok.yml vyapaar-mcp
   ```

---

## 3. Configure RazorpayX Webhook

1.  **Start Tunnel**: Use the command above.
2.  **Copy URL**: Capture the `https://...` forwarding address.
3.  **Update Razorpay**: 
    *   Navigate to **Settings > Webhooks** in RazorpayX.
    *   Set the URL to `https://your-tunnel-id.ngrok-free.app/webhook/razorpay`.
4.  **Rotate Secret**: Use a high-entropy string for the Webhook Secret.
    *   **Best Practice**: Use `openssl rand -hex 32` to generate a secure secret.
    *   **Save As**: `VYAPAAR_RAZORPAY_WEBHOOK_SECRET` in your `.env`.

---

## 4. Cybersecurity Check-List

- [ ] **Shell History**: Check `history | grep ngrok`. If you accidentally ran the token in cleartext, clear your history and rotate the token on the ngrok dashboard.
- [ ] **HTTPS Only**: Always use the `https` forwarding URL. Razorpay will (and should) reject non-SSL endpoints.
- [ ] **IP Whitelisting**: (Optional) In the ngrok dashboard, you can restrict the tunnel to only accept requests from Razorpay's IP ranges if available.
- [ ] **Token Rotation**: Rotate your `NGROK_AUTHTOKEN` every 90 days.
# SSL Certificates for Local Development

This directory contains SSL certificates for HTTPS development on localhost.

## Why HTTPS is Required

ChatPop requires HTTPS in development for:
- **Voice Messages**: Browser `MediaRecorder` API requires secure context
- **WebSocket Security**: WSS (secure WebSocket) connections
- **Mobile Testing**: iOS Safari requires HTTPS for microphone access

## Generating Certificates

### Using mkcert (Recommended)

1. **Install mkcert:**
   ```bash
   # macOS
   brew install mkcert

   # Linux
   sudo apt install mkcert

   # Windows
   choco install mkcert
   ```

2. **Install local CA:**
   ```bash
   mkcert -install
   ```

3. **Generate certificates:**
   ```bash
   cd certs
   mkcert localhost 127.0.0.1 10.0.0.135 ::1
   ```

   This creates:
   - `localhost+3.pem` (certificate)
   - `localhost+3-key.pem` (private key)

### Using OpenSSL (Alternative)

If you prefer OpenSSL:

```bash
cd certs
openssl req -x509 -newkey rsa:4096 -keyout localhost+3-key.pem -out localhost+3.pem -days 365 -nodes -subj "/CN=localhost"
```

**Note:** Browsers will show security warnings with self-signed OpenSSL certs unless you manually trust them.

## Certificate Files

The following files should exist in this directory (gitignored):
- `localhost+3.pem` - Public certificate
- `localhost+3-key.pem` - Private key

**⚠️ Important:** Never commit private keys (`.pem`, `.key`) to version control!

## Troubleshooting

### Certificate Not Trusted
- Run `mkcert -install` to install the local CA
- Restart your browser

### Wrong Hostname
- Regenerate certificates with your machine's IP if testing on mobile
- Example: `mkcert localhost 127.0.0.1 192.168.1.100`

### Port Issues
- Backend uses port **9000** (HTTPS)
- Frontend uses port **4000** (HTTPS)
- Ensure no other services are using these ports

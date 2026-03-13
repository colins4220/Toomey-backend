# W.L. Toomey Irrigation - PDF Generator Backend

Backend server that generates proposal PDFs from iPad estimates and emails them to clients.

## 🚀 One-Click Deploy

### Deploy to Railway (Recommended - Easiest)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/toomey-backend)

1. Click the button above
2. Connect your GitHub account (if needed)
3. Click "Deploy Now"
4. Wait 2 minutes for deployment
5. Go to your project → Variables tab
6. Add these environment variables:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=your-email@gmail.com
BCC_EMAIL=your-email@gmail.com
```

7. Copy your Railway URL (looks like `https://toomey-backend-production.up.railway.app`)
8. Update your iPad app with this URL (see below)

---

### Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Click the button above
2. Connect your GitHub account
3. Click "Apply"
4. Add the same environment variables as above
5. Copy your Render URL
6. Update your iPad app

---

## 📧 Getting Gmail App Password

1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** (required)
3. Go to https://myaccount.google.com/apppasswords
4. Select **"Mail"** → **"Other"** → name it "Toomey Backend"
5. Click **Generate**
6. Copy the 16-character password (remove spaces)
7. Use this as your `SMTP_PASSWORD`

---

## 🔗 Connect iPad App to Backend

1. Open your `index.html` file in Netlify
2. Search for `YOUR-RENDER-URL` (appears twice)
3. Replace with your actual backend URL
4. Example:
   ```javascript
   // Before:
   const BACKEND_URL = 'https://YOUR-RENDER-URL.onrender.com';
   
   // After:
   const BACKEND_URL = 'https://toomey-backend-production.up.railway.app';
   ```
5. Save and re-deploy

---

## ✅ Test It

1. Go to your backend URL + `/health`
   - Example: `https://your-url.railway.app/health`
2. You should see: `{"status":"ok","service":"toomey-pdf-generator"}`
3. If yes ✅ — backend is working!

---

## 📱 Using on iPad

1. Complete an estimate in the app
2. Tap "Generate Proposal"
3. Wait 2-3 seconds
4. Tap "Preview PDF" to verify it looks correct
5. Add optional custom message
6. Tap "Send to Customer"
7. Done! Email sent with PDF attached

---

## 🐛 Troubleshooting

**PDF generation fails:**
- Check Railway/Render logs for errors
- Verify all 4 files are present

**Email doesn't send:**
- Check Gmail App Password is correct (no spaces)
- Verify all SMTP environment variables are set
- Check Gmail security settings

**Backend is slow on first request:**
- Free tier spins down after inactivity
- First request takes 20-30 seconds to wake up
- Subsequent requests are instant

---

## 💰 Cost

**Railway Free Tier:**
- $5 free credit/month
- ~500 hours of uptime
- More than enough for typical use

**Render Free Tier:**
- Spins down after 15 min inactivity
- 750 free hours/month
- First request after idle takes ~30 sec

Upgrade to paid ($5-7/month) for always-on service with instant responses.

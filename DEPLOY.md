# Backend Deployment Guide

This backend lets you:
1. **Generate PDF** from iPad estimate
2. **Preview PDF** on iPad to verify everything looks correct
3. **Send to client** with one tap after approval

---

## 🚀 Deploy to Render.com (Free Tier)

### Step 1: Create Render Account
1. Go to https://render.com
2. Sign up (free)
3. Connect your GitHub account (optional but easier)

### Step 2: Upload Backend Files

**Option A - GitHub (Recommended):**
1. Create a new GitHub repo called `toomey-backend`
2. Upload all files from the `toomey-backend` folder:
   - `server.py`
   - `fill_toomey_pdf.py`
   - `WLToomeyIrrigationProposal.pdf`
   - `requirements.txt`
3. Go to Render → **New → Web Service**
4. Connect your GitHub repo

**Option B - Direct Upload:**
1. Zip the `toomey-backend` folder
2. Go to Render → **New → Web Service**
3. Choose "Public Git repository"
4. Use this dummy repo: `https://github.com/render-examples/flask-hello-world`
5. After deploy, we'll upload your files via Render Shell

### Step 3: Configure Render Service

**Build Command:**
```
pip install -r requirements.txt
```

**Start Command:**
```
gunicorn server:app
```

**Environment:**
- Python 3.11+

### Step 4: Add Environment Variables (For Email)

In Render dashboard, go to **Environment** and add:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
BCC_EMAIL=your-email@gmail.com
```

**Getting Gmail App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication (required)
3. Go to **App Passwords**
4. Generate password for "Mail"
5. Use that 16-character password (not your regular Gmail password)

### Step 5: Deploy

Click **Deploy** and wait ~2 minutes.

Your backend URL will be: `https://toomey-backend.onrender.com`

### Step 6: Test It

Open: `https://toomey-backend.onrender.com/health`

You should see:
```json
{"status": "ok", "service": "toomey-pdf-generator"}
```

---

## 📱 Connect iPad App to Backend

### Step 1: Update the App

In your `index.html`, find the `generate()` function (around line 570) and replace it with:

```javascript
async function generate() {
  setLoading(true);
  
  const estimateData = {
    customer_name: name,
    customer_address: address,
    customer_email: email,
    date: proposalDate,
    hunter_pgp_ultra: String(pgp),
    mp_rotor_nozzle: String(mp),
    hunter_pro4_spray: String(pro4),
    drip_zones: String(drip),
    number_of_zones: String(zones),
    irritrol_valves: String(valves),
    hydrawise_timer: timer,
    price: displayPrice,
    notes: notes,
    sidewalk_strip: sidewalk,
    other_addon: other
  };
  
  try {
    // Generate PDF on backend
    const response = await fetch('https://YOUR-RENDER-URL.onrender.com/generate-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(estimateData)
    });
    
    const result = await response.json();
    
    if (result.success) {
      // Store PDF ID for preview/send flow
      window.generatedPdfId = result.pdf_id;
      window.pdfPreviewUrl = 'https://YOUR-RENDER-URL.onrender.com' + result.preview_url;
      window.pdfDownloadUrl = 'https://YOUR-RENDER-URL.onrender.com' + result.download_url;
    }
    
    setLoading(false);
    setDone(true);
  } catch (err) {
    console.error('PDF generation failed:', err);
    alert('Failed to generate PDF. Please try again.');
    setLoading(false);
  }
}
```

Replace `YOUR-RENDER-URL` with your actual Render URL (without https://).

---

## 🎯 How the Workflow Works

### On iPad:

1. **Complete estimate** → Tap "Generate Proposal"
2. **Backend generates PDF** (takes ~2 seconds)
3. **Done screen shows:**
   - ✅ "Proposal Generated!"
   - 📄 **"Preview PDF"** button (opens PDF in new tab)
   - 📧 **"Send to Client"** button (appears after preview)

4. **Tap "Preview PDF":**
   - Opens the filled PDF in Safari
   - You can zoom, scroll, verify everything is correct
   - If wrong, tap "← Edit" to fix and regenerate

5. **After verifying, tap "Send to Client":**
   - Optional: Add custom message
   - Tap "Send"
   - PDF emails to client
   - You get BCC copy
   - Done!

---

## 💰 Cost

**Render Free Tier:**
- Service spins down after 15 min of inactivity
- First request after idle takes ~30 seconds to wake up
- Unlimited requests once awake
- 750 free hours/month (more than enough)

**To avoid spin-down** (paid):
- Upgrade to $7/month plan
- Service stays always-on
- Instant response every time

---

## 🔧 Troubleshooting

**PDF generation fails:**
- Check Render logs: Dashboard → Logs
- Most common: missing PDF template file

**Email doesn't send:**
- Verify Gmail App Password is correct
- Check SMTP environment variables are set
- Gmail may block first email (check spam/security alerts)

**Backend is slow:**
- First request after idle takes 20-30 sec (free tier)
- Subsequent requests are instant
- Upgrade to paid plan for always-on

---

## 📊 Optional: Log to Google Sheets

Add this after PDF generation in the app:

```javascript
// Also log to Google Sheets
await fetch('YOUR_GOOGLE_APPS_SCRIPT_URL', {
  method: 'POST',
  body: JSON.stringify(estimateData)
});
```

See main README for Google Sheets setup.

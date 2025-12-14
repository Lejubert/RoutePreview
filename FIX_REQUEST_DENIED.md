# 🔧 Fix REQUEST_DENIED Error

Your debug output shows: `This API project is not authorized to use this API.`

Even though you enabled APIs and have billing, this usually means:

---

## ⚡ **Most Likely Cause: Wrong Project**

Your API key belongs to Project A, but you enabled APIs in Project B!

### ✅ Fix (2 minutes):

#### Step 1: Find which project your API key belongs to

1. Go to: https://console.cloud.google.com/apis/credentials
2. Look at the **project dropdown** at the top (next to "Google Cloud")
3. **Write down the project name/ID**

#### Step 2: Make sure APIs are enabled in THAT project

1. While still on that project, click the menu (☰) → "APIs & Services" → "Library"
2. Search and enable these **in the same project**:
   - Geocoding API
   - Directions API
   - Street View Static API

#### Step 3: Make sure billing is linked to THAT project

1. Go to: https://console.cloud.google.com/billing
2. Make sure your billing account is linked to **that same project**

---

## 🔧 **Alternative Fix: Remove API Key Restrictions**

Your API key might have restrictions that block the APIs.

### Steps:

1. Go to: https://console.cloud.google.com/apis/credentials
2. Click on your API key
3. Scroll to **"API restrictions"**:
   - If it says "Restrict key", change to **"Don't restrict key"**
   - Click Save
4. Scroll to **"Application restrictions"**:
   - Set to **"None"**
   - Click Save
5. Wait 2-3 minutes

---

## 🆕 **Nuclear Option: Create Fresh API Key**

If nothing works, create a new API key:

### Steps:

1. Go to: https://console.cloud.google.com/apis/credentials
2. Make sure you're in the **correct project** (check dropdown)
3. Click **"+ CREATE CREDENTIALS"** → "API key"
4. Copy the new key
5. Update your `.env` file:
   ```bash
   GOOGLE_API_KEY=your_new_key_here
   ```
6. Test again:
   ```bash
   python debug_api.py
   ```

---

## 📋 Checklist

Run through this checklist:

- [ ] I'm looking at the **correct project** in Google Cloud Console (check dropdown)
- [ ] My API key was created **in that project** (check credentials page)
- [ ] **Geocoding API** is enabled in that project
- [ ] **Directions API** is enabled in that project
- [ ] **Street View Static API** is enabled in that project
- [ ] Billing account is **linked to that project**
- [ ] API key has **no restrictions** (or includes these 3 APIs)
- [ ] I waited **3-5 minutes** after making changes

---

## 🧪 Test After Each Fix

```bash
cd /Users/aldrinjenson/personal/code/street_view_to_video
./venv/bin/python debug_api.py
```

When it works, you'll see:
```
✅ SUCCESS! API is working!
```

Then run:
```bash
streamlit run app.py
```

---

## 🆘 Still Not Working?

Screenshot and share:
1. Your Google Cloud Console showing the **project name** at the top
2. The **API credentials** page showing your key
3. The **Enabled APIs** page showing Geocoding/Directions/Street View

This will help identify the exact mismatch!


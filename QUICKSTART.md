# 🚀 Quick Start Guide

## ❌ Current Issue

You're seeing: `REQUEST_DENIED - This API project is not authorized to use this API`

**This means your API key is working, but the APIs aren't enabled yet!**

---

## ✅ FIX (5 Minutes)

### Step 1: Run the diagnostic tool

```bash
cd /Users/aldrinjenson/personal/code/street_view_to_video
source venv/bin/activate
pip install colorama
python check_api.py
```

This will show you **exactly** which APIs need to be enabled.

### Step 2: Enable the failing APIs

The script will give you direct links. Click each one and press "ENABLE":

1. **Geocoding API** - Converts addresses to coordinates
2. **Directions API** - Gets routes between points  
3. **Street View Static API** - Fetches Street View images

### Step 3: Enable Billing (Required)

Go to: https://console.cloud.google.com/billing

- Add a credit card
- You get **$200/month FREE**
- Most personal projects stay free

### Step 4: Wait 1-2 minutes

APIs take a minute to activate after enabling.

### Step 5: Test again

```bash
python check_api.py
```

You should see:
```
✅ Geocoding API is working!
✅ Directions API is working!
✅ Street View API is working!
🎉 SUCCESS!
```

### Step 6: Run the app

```bash
streamlit run app.py
```

Select "Times Square → Central Park" from the dropdown and click Generate!

---

## 📖 More Help

- **Detailed setup**: See `SETUP_APIS.md`
- **General docs**: See `README.md`

---

## 🎯 About the `google_streetview` Library

You asked about https://rrwen.github.io/google_streetview/

**We don't need it!** Our custom approach gives you:
- ✅ Better error messages
- ✅ Real-time progress tracking
- ✅ Beautiful UI with Streamlit
- ✅ More control and customization

The library is simpler but **you'd still need to enable the same APIs either way**.

---

## ✨ New Features

Your app now has:
- 📍 **Example routes dropdown** - Easy testing!
- 📊 **Real-time progress** - See elapsed/remaining time
- 🔍 **Terminal logging** - Debug easily
- 💰 **Cost estimator** - Know costs upfront
- ⚠️ **Better errors** - Clear guidance when things fail


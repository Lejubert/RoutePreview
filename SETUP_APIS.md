# 🔑 Enable Google APIs - REQUIRED STEP!

Your error: `REQUEST_DENIED - This API project is not authorized to use this API`

This means your API key exists but **the APIs aren't enabled**.

---

## 📋 Step-by-Step Fix (5 minutes)

### 1. **Go to Google Cloud Console**
https://console.cloud.google.com/

### 2. **Select Your Project**
Click the project dropdown at the top and select your project

### 3. **Enable Each API** 

Click these links and click "ENABLE" on each:

#### ✅ Geocoding API
https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com
- Converts addresses → coordinates

#### ✅ Directions API  
https://console.cloud.google.com/apis/library/directions-backend.googleapis.com
- Gets route between two points

#### ✅ Street View Static API
https://console.cloud.google.com/apis/library/street-view-image-backend.googleapis.com
- Fetches Street View images

### 4. **Enable Billing**
https://console.cloud.google.com/billing

Google requires a credit card but gives you **$200/month FREE** credit

### 5. **Wait 1-2 Minutes**
After enabling, APIs take ~1 min to activate

### 6. **Test Your Setup**

```bash
cd /Users/aldrinjenson/personal/code/street_view_to_video
source venv/bin/activate
pip install colorama
python check_api.py
```

You should see:
```
✅ Geocoding API is working!
✅ Directions API is working!  
✅ Street View API is working!
🎉 All APIs are working!
```

---

## 🚨 Common Issues

### "API not found"
Make sure you're in the **correct project** in the dropdown

### "Billing not enabled"
Add a credit card at https://console.cloud.google.com/billing
(You get $200 free/month)

### Still getting REQUEST_DENIED
1. Double-check you enabled all 3 APIs
2. Wait 2-3 minutes after enabling
3. Refresh your Streamlit app

---

## ✅ Once APIs are enabled

Run: `streamlit run app.py`

The app will work perfectly!


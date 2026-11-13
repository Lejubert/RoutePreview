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

### Google Routes API pour le module Roadbook

Le module Roadbook utilise **Routes API – Compute Routes** pour récupérer des instructions et estimations associées à une trace GPX/KML.

1. Active **Routes API** dans le même projet Google Cloud que la clé utilisée par RoutePreview.
2. Vérifie que la facturation est configurée et que la clé autorise Routes API.
3. Conserve la clé dans les secrets Streamlit ou dans la variable d'environnement `GOOGLE_API_KEY` ; ne la place jamais dans le code ni dans un dépôt public.
4. Dans l'application, ouvre l'onglet **Roadbook**, puis clique sur **Récupérer les directions Google**.

Les points de passage proviennent de la trace et sont envoyés dans leur ordre, avec l'option `via`. Les requêtes sont découpées pour rester à 10 points intermédiaires au maximum. La géométrie et les PK de référence restent ceux du GPX/KML ; les étapes calculées par Google sont comparées à la trace et les écarts supérieurs au seuil choisi sont signalés.

**Important :** le mode DRIVE standard ne constitue pas un profil poids lourd et ne valide ni gabarit, ni masse, ni rayon de giration, ni ouvrages, ni autorisations de transport exceptionnel. Ces contraintes doivent être vérifiées séparément.

Documentation : https://developers.google.com/maps/documentation/routes

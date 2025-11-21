# 🚀 Vercel Deploy Rehberi - TasoFinder

## 📋 Ön Hazırlık

1. **Vercel hesabı oluşturun** (ücretsiz): https://vercel.com
2. **GitHub repository'nizi hazırlayın** (kodlar GitHub'da olmalı)

## 🔧 Deploy Adımları

### Yöntem 1: Vercel Dashboard (Önerilen)

1. **Vercel'e giriş yapın**
   - https://vercel.com/login
   - GitHub hesabınızla giriş yapın

2. **Yeni proje oluşturun**
   - Dashboard'da "Add New" → "Project" tıklayın
   - GitHub repository'nizi seçin: `tasofinder-paraphrase-web-app`
   - "Import" tıklayın

3. **Proje ayarlarını yapın**
   
   **Framework Preset:** Other (veya Python)
   
   **Root Directory:**
   ```
   SynonymFinder
   ```
   ⚠️ **ÖNEMLİ:** Root Directory olarak `SynonymFinder` yazın veya klasörü seçin!
   
   **Build Command:**
   ```
   pip install -r requirements.txt
   ```
   (Veya boş bırakın, Vercel otomatik algılar)
   
   **Output Directory:** (Boş bırakın)
   
   **Install Command:**
   ```
   pip install -r requirements.txt
   ```
   (Veya boş bırakın)

4. **Environment Variables (isteğe bağlı)**
   - Şu an için gerekli yok
   - İleride gerekiyorsa buradan ekleyebilirsiniz

5. **Deploy!**
   - "Deploy" butonuna tıklayın
   - Vercel otomatik olarak deploy edecek (1-2 dakika sürebilir)

### Yöntem 2: Vercel CLI

```bash
# Vercel CLI'yi yükleyin (ilk kez)
npm i -g vercel

# Proje dizinine gidin
cd SynonymFinder

# Vercel'e login olun
vercel login

# Deploy edin
vercel

# Production'a deploy
vercel --prod
```

## ⚙️ Yapılandırma Dosyaları

### ✅ Oluşturulmuş Dosyalar

1. **`vercel.json`** - Vercel yapılandırması
2. **`api/index.py`** - Serverless function handler
3. **`.vercelignore`** - Deploy'da hariç tutulacak dosyalar

### 📁 Proje Yapısı

```
SynonymFinder/
├── api/
│   └── index.py          ← Vercel serverless function
├── app.py                ← Flask uygulaması
├── word_lookup.py        ← Paraphrase mantığı
├── templates/
│   └── index.html        ← Frontend
├── static/               ← CSS, görseller, iconlar
├── vercel.json           ← Vercel yapılandırması
├── requirements.txt      ← Python bağımlılıkları
└── .vercelignore         ← Ignore dosyası
```

## 🔍 Doğrulama

Deploy tamamlandıktan sonra:

1. **Ana sayfayı kontrol edin:**
   ```
   https://your-project.vercel.app
   ```

2. **API endpoint'lerini test edin:**
   ```
   https://your-project.vercel.app/api/lookup?word=example
   ```

3. **Static dosyaları kontrol edin:**
   ```
   https://your-project.vercel.app/static/logo.png
   ```

## ⚠️ Olası Sorunlar ve Çözümleri

### 1. NLTK Verileri İndirme Sorunu

**Sorun:** İlk istekte NLTK verileri indirilemiyor.

**Çözüm:** `word_lookup.py` içinde `_ensure_wordnet_data()` fonksiyonu otomatik indirecektir. İlk istek biraz yavaş olabilir.

### 2. Timeout Hatası

**Sorun:** Uzun paraphrase işlemleri timeout veriyor.

**Çözüm:** 
- Vercel Free tier: 10 saniye timeout
- Hobby tier: 60 saniye timeout
- Uzun işlemler için NLTK verilerini önceden indirin

### 3. Memory Hatası

**Sorun:** Büyük cümleler için memory hatası.

**Çözüm:**
- Memory limit: Vercel Free tier 1GB
- Daha büyük cümleleri parçalara bölün

### 4. Static Dosyalar Görünmüyor

**Sorun:** CSS, görseller yüklenmiyor.

**Çözüm:**
- `vercel.json` içinde static route'ları kontrol edin
- `app.py` içinde `static_folder` ayarını kontrol edin

### 5. Module Not Found Hatası

**Sorun:** Python modülleri bulunamıyor.

**Çözüm:**
- `requirements.txt` içinde tüm bağımlılıklar olmalı
- Deploy loglarını kontrol edin

## 📊 Performans Optimizasyonu

### 1. NLTK Verilerini Önceden İndirin

`vercel.json` içine build command ekleyin:

```json
{
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb"
      }
    }
  ]
}
```

### 2. Cache Kullanımı

Vercel otomatik olarak static dosyaları cache'ler. API endpoint'leri için cache stratejisi uygulayabilirsiniz.

### 3. Cold Start Azaltma

- NLTK verilerini önceden yükleyin
- İlk istekten sonra lambda warm kalır
- Keep-alive kullanın (pro plan)

## 🔗 Kaynaklar

- [Vercel Python Runtime](https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python)
- [Vercel Flask Örneği](https://github.com/vercel/examples/tree/main/python/flask)
- [Vercel Dokümantasyonu](https://vercel.com/docs)

## 📞 Destek

Sorun yaşarsanız:
1. Vercel Dashboard'dan Logs bölümünü kontrol edin
2. Build loglarını inceleyin
3. GitHub Issues'da sorun bildirin

## ✅ Deployment Checklist

- [ ] GitHub repository hazır
- [ ] `vercel.json` dosyası oluşturuldu
- [ ] `api/index.py` dosyası oluşturuldu
- [ ] `requirements.txt` güncel
- [ ] Root Directory: `SynonymFinder` ayarlandı
- [ ] Deploy edildi
- [ ] Ana sayfa çalışıyor
- [ ] API endpoint'leri çalışıyor
- [ ] Static dosyalar yükleniyor

---

**🎉 Başarılı deployment sonrası URL'niz:** `https://your-project.vercel.app`


# Setup Guide — Personal Bot & AI Agent (GitHub Only Architecture)

এই প্রজেক্টটি সম্পূর্ণ নিজের একার ব্যবহারের (Single-user) জন্য তৈরি। এতে কোনো লগইন বা মাল্টি-ইউজার জটিলতা নেই। শুধুমাত্র GitHub ব্যবহার করে ফ্রন্টএন্ড, ব্যাকএন্ড ও ফাইল-ভিত্তিক স্টোরেজ পরিচালনা করা হয়—যেখানে ব্যাকএন্ডের জন্য **GitHub Actions** ও **GitHub Codespaces** ব্যবহৃত হয়।

## ১. GitHub Repository ও Branch নিয়ম
- মূল ও একমাত্র ব্রাঞ্চ হলো `main`। নতুন কোনো ব্রাঞ্চ তৈরি না করে সব আপডেট সরাসরি `main` ব্রাঞ্চে রাখুন।
- কোনো API Key বা গোপন তথ্য কোডে বা রিপোজিটরিতে সরাসরি যুক্ত করবেন না।

## ২. Root `.github/workflows/` সেটআপ
- GitHub Actions স্বয়ংক্রিয়ভাবে চালাতে workflow ফাইলগুলো রিপোজিটরির Root-এর `.github/workflows/` ফোল্ডারে রাখুন (`scheduled-tasks.yml`, `brain-reverify.yml`, `backup-sync.yml`)।
- `personal-bot-agent/.github/workflows/`-এ কোনো ডুপ্লিকেট ফাইল থাকলে তা পরিষ্কার রাখুন।

## ৩. GitHub Codespaces-এ চালানোর নিয়ম
1. `rjbaiwork-netizen/AI-Agent` রিপোজিটরি থেকে **GitHub Codespaces** চালু করুন।
2. নিচের কমান্ড দিয়ে প্রয়োজনীয় প্যাকেজ ইনস্টল ও কনফিগারেশন ফাইল প্রস্তুত করুন:
   ```bash
   cd personal-bot-agent
   pip install -r requirements.txt
   cp .env.example .env
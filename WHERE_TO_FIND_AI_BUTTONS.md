# 🔍 Where to Find AI Assistant Buttons - Step by Step

## 🚨 **Important: You Need to Go to the RIGHT Page!**

The AI Assistant buttons are on the **dedicated patients list page**, not the dashboard.

---

## 📍 **Step-by-Step Instructions:**

### **Step 1: Navigate to Patients List**

1. **In your browser, go to:** `[your-domain]/patients`

   - Example: `http://localhost:5000/patients`
   - Or: `https://yourdomain.com/patients`

2. **OR look for a "Patients" menu item** in your navigation
3. **OR look for a "Patient List" or "View All Patients" link**

### **Step 2: You Should See a Table Like This:**

```
| ☐ | Name     | Diagnosis    | Last Visit | Status | Actions     |
|---|----------|--------------|------------|--------|-------------|
| ☐ | Peter    | Back pain    | 2024-01-15 | Active | [🤖] [👁️]  |
| ☐ | Maria    | Knee pain    | 2024-01-10 | Active | [🤖] [👁️]  |
| ☐ | John     | Shoulder     | 2024-01-12 | Active | [🤖] [👁️]  |
```

### **Step 3: Look for the Actions Column**

- **Last column on the right**
- **Two small buttons per patient:**
  - **🤖 Blue robot icon** = AI Assistant
  - **👁️ Eye icon** = View Details

---

## ⚠️ **Common Mistakes:**

### **❌ Wrong Page - Dashboard/Home**

If you see:

- Today's appointments
- Statistics cards
- Recent activity
- **BUT NO patient table with Actions column**

**👉 You're on the wrong page! Go to `/patients` instead.**

### **❌ Wrong Page - Individual Patient**

If you see:

- One patient's details
- Treatment history
- Add treatment button
- **BUT NO list of multiple patients**

**👉 You're viewing a single patient. Go back to `/patients` for the list.**

---

## 🧪 **Troubleshooting:**

### **Test 1: Check URL**

- Make sure your browser URL ends with `/patients`
- Not `/dashboard`, `/`, or `/patient/123`

### **Test 2: Hard Refresh**

- **Windows:** Ctrl + F5
- **Mac:** Cmd + Shift + R
- **Chrome:** Right-click reload → "Empty Cache and Hard Reload"

### **Test 3: Private/Incognito Mode**

- Open a new incognito/private window
- Log in again
- Go to `/patients`

### **Test 4: Browser Console**

- Press F12 to open developer tools
- Look for any JavaScript errors in the Console tab
- If you see errors, that might be preventing the buttons from showing

---

## 🎯 **Exact URLs to Try:**

Replace `[your-domain]` with your actual domain:

- **Local development:** `http://localhost:5000/patients`
- **Production:** `https://yourdomain.com/patients`

---

## 🤔 **Still Can't Find It?**

### **Option 1: Navigation Menu**

Look for these menu items:

- "Patients"
- "Patient List"
- "View Patients"
- "All Patients"

### **Option 2: Search for Links**

Look for any links that say:

- "Patients"
- "Patient Management"
- "View All Patients"

### **Option 3: Check Your Navigation**

The patients list should be accessible from your main navigation menu.

---

**💡 The key is making sure you're on the `/patients` page (the list view), not the dashboard or individual patient pages!**

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

const resources = {
  ar: {
    translation: {
      app: { name: 'SMSES', tagline: 'نظام المبيعات والهندسة الطبية' },
      login: { title: 'تسجيل الدخول', email: 'البريد الإلكتروني', password: 'كلمة المرور', otp: 'رمز التحقق (MFA)', submit: 'دخول', otpRequired: 'أدخل رمز التحقق من تطبيق المصادقة', failed: 'بيانات الدخول غير صحيحة', locked: 'الحساب مقفل مؤقتاً' },
      nav: { dashboard: 'لوحة التحكم', users: 'المستخدمون', audit: 'سجل التدقيق', logout: 'خروج', language: 'English' },
      common: { loading: 'جاري التحميل…', empty: 'لا توجد بيانات', create: 'إضافة', save: 'حفظ', cancel: 'إلغاء', active: 'نشط', inactive: 'معطّل', search: 'بحث', noAccess: 'لا تملك صلاحية لهذه الصفحة', error: 'حدث خطأ' },
      users: { title: 'المستخدمون', email: 'البريد', name: 'الاسم', roles: 'الأدوار', status: 'الحالة', password: 'كلمة المرور', new: 'مستخدم جديد' },
      audit: { title: 'سجل التدقيق', when: 'الوقت', who: 'المستخدم', action: 'الإجراء', entity: 'الكيان', summary: 'الملخص' },
      dashboard: { welcome: 'مرحباً', hint: 'ستظهر هنا مؤشرات المبيعات والذمم والمخزون حسب صلاحياتك.' },
    },
  },
  en: {
    translation: {
      app: { name: 'SMSES', tagline: 'Medical Sales & Engineering System' },
      login: { title: 'Sign in', email: 'Email', password: 'Password', otp: 'One-time code (MFA)', submit: 'Sign in', otpRequired: 'Enter the code from your authenticator app', failed: 'Invalid credentials', locked: 'Account temporarily locked' },
      nav: { dashboard: 'Dashboard', users: 'Users', audit: 'Audit log', logout: 'Sign out', language: 'العربية' },
      common: { loading: 'Loading…', empty: 'No data', create: 'Add', save: 'Save', cancel: 'Cancel', active: 'Active', inactive: 'Disabled', search: 'Search', noAccess: 'You do not have access to this page', error: 'Something went wrong' },
      users: { title: 'Users', email: 'Email', name: 'Name', roles: 'Roles', status: 'Status', password: 'Password', new: 'New user' },
      audit: { title: 'Audit log', when: 'When', who: 'User', action: 'Action', entity: 'Entity', summary: 'Summary' },
      dashboard: { welcome: 'Welcome', hint: 'Sales, receivables and stock indicators will appear here based on your permissions.' },
    },
  },
}

export function applyDirection(lng: string) {
  document.documentElement.lang = lng
  document.documentElement.dir = lng === 'ar' ? 'rtl' : 'ltr' // real RTL/LTR, not just alignment
}

const saved = localStorage.getItem('lang') ?? 'ar'
i18n.use(initReactI18next).init({ resources, lng: saved, fallbackLng: 'en', interpolation: { escapeValue: false } })
applyDirection(saved)
i18n.on('languageChanged', (lng) => {
  localStorage.setItem('lang', lng)
  applyDirection(lng)
})

export default i18n

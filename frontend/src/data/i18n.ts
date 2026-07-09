/**
 * Investigation narrative in EN / HI / GU.
 * In production these render through the IndicTrans2 pipeline (CLAUDE.md §1.4);
 * for the UI demo they are pre-rendered strings.
 */

export type Lang = 'en' | 'hi' | 'gu'

export const LANG_OPTIONS: { value: Lang; label: string }[] = [
  { value: 'en', label: 'EN' },
  { value: 'hi', label: 'हिंदी' },
  { value: 'gu', label: 'ગુજરાતી' },
]

type Narrative = {
  technical: string
  founder: string
  impact: { label: string; value: string; hint: string }[]
  decision: string
}

export const NARRATIVE: Record<Lang, Narrative> = {
  en: {
    technical:
      'At 03:11 IST, priya.sharma\'s account authenticated from Moscow 4.4 hours after a Bengaluru login — a physical impossibility. The attacker cleared MFA through push fatigue, minted GitHub PAT #4821 for persistence, and recovered a live AWS key from paykraft-infra\'s commit history. At 03:31 they began pulling customers-db-backups (2.3 GB, 412k customer records). ViltrumX revoked the session, rotated the key, and blocked the source IP mid-transfer — zero objects were exfiltrated. One decision remains with you: disabling Priya\'s account entirely (L4 proposal).',
    founder:
      'Someone stole your CTO\'s login and tried to download your entire customer database at 3 AM from Russia. We stopped it before a single record left. Her account is safe to use again once she resets her password — but we recommend you approve a temporary account freeze until she confirms her laptop is clean.',
    impact: [
      { label: 'Data protected', value: '412k records', hint: 'full customer PII set — zero exfiltrated' },
      { label: 'Exposure avoided', value: '₹3.2 Cr', hint: 'estimated breach cost (notification, churn, forensics)' },
      { label: 'Max DPDP penalty averted', value: '₹250 Cr', hint: 'statutory ceiling for a personal-data breach' },
      { label: 'CERT-In clock', value: '5h 27m left', hint: 'report already drafted — one click to file' },
    ],
    decision: 'Approve the proposed freeze of priya.sharma\'s account?',
  },
  hi: {
    technical:
      'सुबह 03:11 IST पर priya.sharma का खाता बेंगलुरु लॉगिन के केवल 4.4 घंटे बाद मास्को से प्रमाणित हुआ — जो शारीरिक रूप से असंभव है। हमलावर ने बार-बार MFA अनुरोध भेजकर पुष्टि करवाई, स्थायी पहुँच के लिए GitHub PAT #4821 बनाया, और paykraft-infra की कमिट हिस्ट्री से सक्रिय AWS कुंजी निकाली। 03:31 पर उसने customers-db-backups (2.3 GB, 4.12 लाख ग्राहक रिकॉर्ड) डाउनलोड करना शुरू किया। ViltrumX ने सत्र रद्द किया, कुंजी बदली और स्रोत IP को बीच में ही ब्लॉक कर दिया — एक भी रिकॉर्ड बाहर नहीं गया। एक निर्णय आपके पास है: प्रिया का खाता पूरी तरह निष्क्रिय करना (L4 प्रस्ताव)।',
    founder:
      'किसी ने आपकी CTO का लॉगिन चुराकर रात 3 बजे रूस से आपका पूरा ग्राहक डेटाबेस डाउनलोड करने की कोशिश की। एक भी रिकॉर्ड बाहर जाने से पहले हमने इसे रोक दिया। पासवर्ड रीसेट के बाद उनका खाता फिर से सुरक्षित है — लेकिन हमारी सलाह है कि जब तक वे पुष्टि न करें कि उनका लैपटॉप सुरक्षित है, तब तक खाते पर अस्थायी रोक को मंज़ूरी दें।',
    impact: [
      { label: 'सुरक्षित डेटा', value: '4.12 लाख रिकॉर्ड', hint: 'पूरा ग्राहक PII सेट — कुछ भी बाहर नहीं गया' },
      { label: 'टला हुआ नुकसान', value: '₹3.2 करोड़', hint: 'अनुमानित उल्लंघन लागत (सूचना, ग्राहक हानि, जाँच)' },
      { label: 'अधिकतम DPDP जुर्माना टला', value: '₹250 करोड़', hint: 'व्यक्तिगत डेटा उल्लंघन की वैधानिक सीमा' },
      { label: 'CERT-In समयसीमा', value: '5 घं 27 मि शेष', hint: 'रिपोर्ट तैयार है — एक क्लिक में दर्ज करें' },
    ],
    decision: 'priya.sharma के खाते पर प्रस्तावित रोक को मंज़ूरी दें?',
  },
  gu: {
    technical:
      'સવારે 03:11 IST વાગ્યે priya.sharma નું ખાતું બેંગલુરુ લૉગિનના માત્ર 4.4 કલાક પછી મોસ્કોથી પ્રમાણિત થયું — જે શારીરિક રીતે અશક્ય છે. હુમલાખોરે વારંવાર MFA વિનંતીઓ મોકલીને મંજૂરી મેળવી, કાયમી પ્રવેશ માટે GitHub PAT #4821 બનાવ્યું, અને paykraft-infra ની કમિટ હિસ્ટ્રીમાંથી સક્રિય AWS કી મેળવી. 03:31 વાગ્યે તેણે customers-db-backups (2.3 GB, 4.12 લાખ ગ્રાહક રેકોર્ડ) ડાઉનલોડ કરવાનું શરૂ કર્યું. ViltrumX એ સત્ર રદ કર્યું, કી બદલી અને સ્રોત IP ને વચ્ચે જ બ્લૉક કરી દીધું — એક પણ રેકોર્ડ બહાર ગયો નથી. એક નિર્ણય તમારો છે: પ્રિયાનું ખાતું સંપૂર્ણ નિષ્ક્રિય કરવું (L4 દરખાસ્ત).',
    founder:
      'કોઈએ તમારા CTO નું લૉગિન ચોરીને રાત્રે 3 વાગ્યે રશિયાથી તમારો આખો ગ્રાહક ડેટાબેઝ ડાઉનલોડ કરવાનો પ્રયાસ કર્યો. એક પણ રેકોર્ડ બહાર જાય તે પહેલાં અમે તેને રોકી દીધો. પાસવર્ડ રીસેટ પછી તેમનું ખાતું ફરી સુરક્ષિત છે — પણ અમારી ભલામણ છે કે તેઓ પોતાનું લેપટોપ સુરક્ષિત હોવાની પુષ્ટિ ન કરે ત્યાં સુધી ખાતા પર કામચલાઉ રોકને મંજૂરી આપો.',
    impact: [
      { label: 'સુરક્ષિત ડેટા', value: '4.12 લાખ રેકોર્ડ', hint: 'સંપૂર્ણ ગ્રાહક PII સેટ — કંઈ બહાર ગયું નથી' },
      { label: 'ટળેલું નુકસાન', value: '₹3.2 કરોડ', hint: 'અંદાજિત ભંગ ખર્ચ (સૂચના, ગ્રાહક નુકસાન, તપાસ)' },
      { label: 'મહત્તમ DPDP દંડ ટળ્યો', value: '₹250 કરોડ', hint: 'વ્યક્તિગત ડેટા ભંગ માટે કાયદાકીય મર્યાદા' },
      { label: 'CERT-In સમયમર્યાદા', value: '5 ક 27 મિ બાકી', hint: 'રિપોર્ટ તૈયાર છે — એક ક્લિકમાં ફાઇલ કરો' },
    ],
    decision: 'priya.sharma ના ખાતા પર સૂચિત રોકને મંજૂરી આપશો?',
  },
}

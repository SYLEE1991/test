export default function Header({ t, lang, setLang }) {
  return (
    <div className="header">
      <h1>{t.appTitle}</h1>
      <div className="header-right">
        <select
          className="lang-select"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
        >
          <option value="en">{t.english}</option>
          <option value="ko">{t.korean}</option>
        </select>
        <div className="user-info">
          <span className="user-icon">👤</span>
          <span>admin</span>
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ProductTable from './components/ProductTable';
import translations from './i18n/translations';
import initialProducts from './data/products';
import './App.css';

function App() {
  const [lang, setLang] = useState('en');
  const [products, setProducts] = useState(initialProducts);
  const t = translations[lang];

  return (
    <div className="app">
      <Sidebar t={t} />
      <div className="main">
        <Header t={t} lang={lang} setLang={setLang} />
        <div className="content">
          <ProductTable products={products} setProducts={setProducts} t={t} />
        </div>
      </div>
    </div>
  );
}

export default App;

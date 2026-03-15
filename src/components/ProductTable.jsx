import { useState } from 'react';

const PAGE_SIZE = 5;

export default function ProductTable({ products, setProducts, t }) {
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({ price: '', salePrice: '' });
  const [searchTerm, setSearchTerm] = useState('');
  const [category, setCategory] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const [updating, setUpdating] = useState(false);

  const categories = ['All', ...new Set(products.map((p) => p.category))];

  const filtered = products.filter((p) => {
    const matchesSearch =
      p.productName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.productCode.includes(searchTerm);
    const matchesCategory = category === 'All' || p.category === category;
    return matchesSearch && matchesCategory;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageProducts = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  const handleEdit = (product) => {
    setEditingId(product.id);
    setEditValues({ price: product.price, salePrice: product.salePrice });
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValues({ price: '', salePrice: '' });
  };

  const handleUpdate = async (product) => {
    setUpdating(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 500));
      setProducts((prev) =>
        prev.map((p) =>
          p.id === product.id
            ? {
                ...p,
                price: parseFloat(editValues.price),
                salePrice: parseFloat(editValues.salePrice),
              }
            : p
        )
      );
      setEditingId(null);
      alert(t.updateSuccess);
    } catch {
      alert(t.updateError);
    } finally {
      setUpdating(false);
    }
  };

  const from = filtered.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const to = Math.min(currentPage * PAGE_SIZE, filtered.length);

  return (
    <div className="product-section">
      <div className="product-header">
        <h2>{t.productList}</h2>
        <button className="btn-add">{t.addNewProduct}</button>
      </div>

      <div className="product-toolbar">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder={t.searchProduct}
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
          />
          {searchTerm && (
            <button className="search-clear" onClick={() => setSearchTerm('')}>
              ✕
            </button>
          )}
        </div>
        <select
          className="category-select"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setCurrentPage(1);
          }}
        >
          <option value="All">{t.allCategories}</option>
          {categories
            .filter((c) => c !== 'All')
            .map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
        </select>
      </div>

      <div className="table-wrapper">
        <table className="product-table">
          <thead>
            <tr>
              <th>{t.productCode}</th>
              <th>{t.productName}</th>
              <th>{t.price}</th>
              <th>{t.salePrice}</th>
              <th>{t.actions}</th>
            </tr>
          </thead>
          <tbody>
            {pageProducts.map((product) => (
              <tr key={product.id}>
                <td>{product.productCode}</td>
                <td>{product.productName}</td>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="number"
                      step="0.01"
                      className="edit-input"
                      value={editValues.price}
                      onChange={(e) =>
                        setEditValues((v) => ({ ...v, price: e.target.value }))
                      }
                    />
                  ) : (
                    product.price.toFixed(2)
                  )}
                </td>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="number"
                      step="0.01"
                      className="edit-input"
                      value={editValues.salePrice}
                      onChange={(e) =>
                        setEditValues((v) => ({
                          ...v,
                          salePrice: e.target.value,
                        }))
                      }
                    />
                  ) : (
                    product.salePrice.toFixed(2)
                  )}
                </td>
                <td>
                  {editingId === product.id ? (
                    <div className="action-buttons">
                      <button
                        className="btn-update"
                        onClick={() => handleUpdate(product)}
                        disabled={updating}
                      >
                        {t.update}
                      </button>
                      <button className="btn-cancel" onClick={handleCancel}>
                        {t.cancel}
                      </button>
                    </div>
                  ) : (
                    <button
                      className="btn-edit"
                      onClick={() => handleEdit(product)}
                    >
                      {t.edit}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-footer">
        <span>{t.showingEntries(from, to, filtered.length)}</span>
        <div className="pagination">
          <button
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => p - 1)}
          >
            {t.previous}
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              className={currentPage === page ? 'active' : ''}
              onClick={() => setCurrentPage(page)}
            >
              {page}
            </button>
          ))}
          <button
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => p + 1)}
          >
            {t.next}
          </button>
        </div>
      </div>
    </div>
  );
}

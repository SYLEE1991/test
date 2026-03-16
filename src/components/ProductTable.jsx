import { useState, useCallback } from 'react';
import { updateProduct } from '../api/productApi';
import Toast from './Toast';

const PAGE_SIZE = 5;

export default function ProductTable({ products, setProducts, t }) {
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({
    productCode: '',
    productName: '',
    price: '',
    salePrice: '',
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [category, setCategory] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const [updating, setUpdating] = useState(false);
  const [isNewRow, setIsNewRow] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = useCallback((message, type) => {
    setToast({ message, type });
  }, []);

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
    setIsNewRow(false);
    setEditValues({
      productCode: product.productCode,
      productName: product.productName,
      price: product.price,
      salePrice: product.salePrice,
    });
  };

  const handleCancel = () => {
    if (isNewRow) {
      setProducts((prev) => prev.filter((p) => p.id !== editingId));
    }
    setEditingId(null);
    setIsNewRow(false);
    setEditValues({ productCode: '', productName: '', price: '', salePrice: '' });
  };

  const handleAddNew = () => {
    const newId = Math.max(...products.map((p) => p.id), 0) + 1;
    const newProduct = {
      id: newId,
      productCode: '',
      productName: '',
      price: 0,
      salePrice: 0,
      category: 'Food',
    };
    setProducts((prev) => [newProduct, ...prev]);
    setEditingId(newId);
    setIsNewRow(true);
    setEditValues({ productCode: '', productName: '', price: '', salePrice: '' });
    setCurrentPage(1);
    setSearchTerm('');
    setCategory('All');
  };

  const handleUpdate = async (product) => {
    if (!editValues.productCode || !editValues.productName) return;
    setUpdating(true);
    try {
      await updateProduct(editValues);

      setProducts((prev) =>
        prev.map((p) =>
          p.id === product.id
            ? {
                ...p,
                productCode: editValues.productCode,
                productName: editValues.productName,
                price: parseFloat(editValues.price) || 0,
                salePrice: parseFloat(editValues.salePrice) || 0,
              }
            : p
        )
      );
      setEditingId(null);
      setIsNewRow(false);
      showToast(isNewRow ? t.createSuccess : t.updateSuccess, 'success');
    } catch (err) {
      showToast(`${t.updateError} (${err.message})`, 'error');
    } finally {
      setUpdating(false);
    }
  };

  const from = filtered.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const to = Math.min(currentPage * PAGE_SIZE, filtered.length);

  return (
    <div className="product-section">
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <div className="product-header">
        <h2>{t.productList}</h2>
        <button className="btn-add" onClick={handleAddNew} disabled={isNewRow}>
          {t.addNewProduct}
        </button>
      </div>

      <div className="product-toolbar">
        <div className="search-box">
          <span className="search-icon">&#128269;</span>
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
              &#10005;
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
              <tr key={product.id} className={editingId === product.id && isNewRow ? 'new-row' : ''}>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="text"
                      className="edit-input edit-input-text"
                      value={editValues.productCode}
                      placeholder={t.productCode}
                      onChange={(e) =>
                        setEditValues((v) => ({ ...v, productCode: e.target.value }))
                      }
                    />
                  ) : (
                    product.productCode
                  )}
                </td>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="text"
                      className="edit-input edit-input-text"
                      value={editValues.productName}
                      placeholder={t.productName}
                      onChange={(e) =>
                        setEditValues((v) => ({ ...v, productName: e.target.value }))
                      }
                    />
                  ) : (
                    product.productName
                  )}
                </td>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="number"
                      step="0.01"
                      className="edit-input"
                      value={editValues.price}
                      placeholder="0.00"
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
                      placeholder="0.00"
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
                        {updating ? t.updating || '...' : t.update}
                      </button>
                      <button className="btn-cancel" onClick={handleCancel} disabled={updating}>
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

      {updating && (
        <div className="loading-overlay">
          <div className="spinner" />
        </div>
      )}

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

const API_URL = '/api/product';
const API_TOKEN = import.meta.env.VITE_API_TOKEN;

function getLayoutId(price, salePrice) {
  if (salePrice !== 0 && salePrice < price) {
    return 'demo_sale';
  }
  return 'demo_normal';
}

export async function updateProduct({ productCode, productName, price, salePrice }) {
  const priceNum = parseFloat(price) || 0;
  const salePriceNum = parseFloat(salePrice) || 0;

  const body = {
    product: [
      {
        layoutId: getLayoutId(priceNum, salePriceNum),
        nfc: 'www.partronesl.com',
        prCode: productCode,
        prInfo: [productCode, productName, String(priceNum), String(salePriceNum)],
        secondCode: '',
      },
    ],
    storeCode: 'test',
    taskId: -1,
  };

  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Access-Token': API_TOKEN,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

# Frontend Changes Guide

## Task 1: Add Edit/Delete to Dividends Page

### Changes to `templates/dividends.html`:

1. **Add Actions column to table header** (around line 396):
```html
<th>Actions</th>
```

2. **Add Actions column to table rows** (in the renderTable function, around line 407):
```html
<td>
    <button class="action-btn edit-btn" onclick="editDividend(${div.id})">Edit</button>
    <button class="action-btn delete-btn" onclick="deleteDividend(${div.id})">Delete</button>
</td>
```

3. **Add Edit modal** (after the Add modal, around line 414):
Change the modal ID from "addDividendModal" to "dividendModal" and add a hidden input for ID:
```html
<input type="hidden" id="dividendId">
```

Also change modal title to be dynamic:
```html
<h2 id="modalTitle">Add New Dividend</h2>
```

4. **Add CSS for action buttons** (in the style section):
```css
.action-btn {
    padding: 6px 12px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.85rem;
    margin-right: 5px;
    transition: all 0.2s ease;
}
.edit-btn { background: #667eea; color: white; }
.edit-btn:hover { background: #5568d3; }
.delete-btn { background: #ef4444; color: white; }
.delete-btn:hover { background: #dc2626; }
```

5. **Add JavaScript functions** (in the script section):

```javascript
let editingDividendId = null;

function openAddModal() {
    editingDividendId = null;
    document.getElementById('modalTitle').textContent = 'Add New Dividend';
    document.getElementById('dividendForm').reset();
    document.getElementById('date').valueAsDate = new Date();
    document.getElementById('dividendModal').classList.add('active');
}

function editDividend(id) {
    const dividend = allDividends.find(d => d.id === id);
    if (!dividend) return;

    editingDividendId = id;
    document.getElementById('modalTitle').textContent = 'Edit Dividend';
    document.getElementById('date').value = dividend.date;
    document.getElementById('ticker').value = dividend.ticker;
    document.getElementById('name').value = dividend.name;
    document.getElementById('isEtf').value = dividend.is_etf ? '1' : '0';
    document.getElementById('grossAmount').value = dividend.gross_amount;
    document.getElementById('foreignTax').value = dividend.foreign_tax;
    document.getElementById('collectionFee').value = dividend.collection_fee;
    document.getElementById('withholdingTax').value = dividend.withholding_tax;
    document.getElementById('vat').value = dividend.vat;
    document.getElementById('totalDividend').value = dividend.total_dividend;
    document.getElementById('dividendModal').classList.add('active');
}

async function deleteDividend(id) {
    if (!confirm('Are you sure you want to delete this dividend?')) return;

    try {
        const response = await fetch(`/api/dividends/${id}`, { method: 'DELETE' });
        const result = await response.json();

        if (result.success) {
            await loadDividends();
        } else {
            alert('Error deleting dividend: ' + result.message);
        }
    } catch (error) {
        console.error('Error deleting dividend:', error);
        alert('Error deleting dividend');
    }
}

// Update saveDividend function to handle both add and edit:
async function saveDividend(event) {
    event.preventDefault();

    const dividendData = {
        date: document.getElementById('date').value,
        ticker: document.getElementById('ticker').value.toUpperCase(),
        name: document.getElementById('name').value,
        is_etf: parseInt(document.getElementById('isEtf').value),
        gross_amount: parseFloat(document.getElementById('grossAmount').value),
        currency_before: document.getElementById('currencyBefore').value || '',
        exchange_rate: parseFloat(document.getElementById('exchangeRate').value) || 0,
        currency_after: document.getElementById('currencyAfter').value || 'EUR',
        foreign_tax: parseFloat(document.getElementById('foreignTax').value) || 0,
        collection_fee: parseFloat(document.getElementById('collectionFee').value) || 0,
        withholding_tax: parseFloat(document.getElementById('withholdingTax').value) || 0,
        vat: parseFloat(document.getElementById('vat').value) || 0,
        total_dividend: parseFloat(document.getElementById('totalDividend').value)
    };

    try {
        const url = editingDividendId ? `/api/dividends/${editingDividendId}` : '/api/dividends';
        const method = editingDividendId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dividendData)
        });

        const result = await response.json();

        if (result.success) {
            closeAddModal();
            await loadDividends();
            alert(editingDividendId ? 'Dividend updated successfully!' : 'Dividend added successfully!');
        } else {
            alert('Error saving dividend: ' + result.message);
        }
    } catch (error) {
        console.error('Error saving dividend:', error);
        alert('Error saving dividend: ' + error.message);
    }
}
```

## Task 2: Add "Add Transaction" Button to Transactions Page

### Changes to `templates/transactions.html`:

1. **Update header section** (around line 584):
```html
<header>
    <div></div>
    <div class="header-content">
        <h1>Transaction History</h1>
        <p>View and manage all your investment transactions</p>
    </div>
    <button class="btn btn-primary" onclick="openAddTransactionModal()">+ Add Transaction</button>
</header>
```

2. **Add CSS for button** (if not already there):
```css
.btn-primary {
    padding: 12px 30px;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1rem;
    background: white;
    color: #667eea;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}
.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}
```

3. **Add modal for new transaction** (before closing body tag):
```html
<!-- Add Transaction Modal -->
<div id="addTransactionModal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <h2>Add New Transaction</h2>
            <button class="close-btn" onclick="closeAddTransactionModal()">&times;</button>
        </div>
        <form id="newTransactionForm" onsubmit="saveNewTransaction(event)">
            <div class="form-group">
                <label for="newDate">Date *</label>
                <input type="date" id="newDate" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label for="newTicker">Ticker *</label>
                    <input type="text" id="newTicker" required placeholder="AAPL">
                </div>
                <div class="form-group">
                    <label for="newName">Name *</label>
                    <input type="text" id="newName" required placeholder="Apple Inc.">
                </div>
            </div>
            <div class="form-group">
                <label for="newAction">Action *</label>
                <select id="newAction" required>
                    <option value="BUY">Buy</option>
                    <option value="SELL">Sell</option>
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label for="newPrice">Price (€) *</label>
                    <input type="number" id="newPrice" step="0.01" required placeholder="150.00">
                </div>
                <div class="form-group">
                    <label for="newQuantity">Quantity *</label>
                    <input type="number" id="newQuantity" step="1" required placeholder="10">
                </div>
            </div>
            <div class="form-group">
                <label for="newTotalPurchasePrice">Total Purchase Price (€) *</label>
                <input type="number" id="newTotalPurchasePrice" step="0.01" required placeholder="1500.00">
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-secondary" onclick="closeAddTransactionModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Add Transaction</button>
            </div>
        </form>
    </div>
</div>
```

4. **Add JavaScript functions** (in script section):
```javascript
function openAddTransactionModal() {
    document.getElementById('newTransactionForm').reset();
    document.getElementById('newDate').valueAsDate = new Date();
    document.getElementById('addTransactionModal').classList.add('active');
}

function closeAddTransactionModal() {
    document.getElementById('addTransactionModal').classList.remove('active');
}

async function saveNewTransaction(event) {
    event.preventDefault();

    const price = parseFloat(document.getElementById('newPrice').value);
    const quantity = parseInt(document.getElementById('newQuantity').value);
    const totalPrice = parseFloat(document.getElementById('newTotalPurchasePrice').value);

    const transactionData = {
        date: document.getElementById('newDate').value,
        ticker: document.getElementById('newTicker').value.toUpperCase(),
        name: document.getElementById('newName').value,
        action: document.getElementById('newAction').value,
        price: price,
        quantity: quantity,
        total_purchase_price: totalPrice,
        price_before_currency: '',
        currency_from: '',
        exchange_rate: '',
        currency_to: 'EUR',
        total_amount_bt: '',
        brokerage_fee: '',
        stock_market_fee: ''
    };

    try {
        // Note: You'll need to add a POST endpoint for transactions in the backend
        // For now, this will use the existing investments endpoint structure
        const response = await fetch('/api/transactions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(transactionData)
        });

        const result = await response.json();

        if (result.success || response.ok) {
            closeAddTransactionModal();
            await loadTransactions();
            alert('Transaction added successfully!');
        } else {
            alert('Error adding transaction: ' + (result.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error adding transaction:', error);
        alert('Error adding transaction: ' + error.message);
    }
}
```

**Note**: You'll need to add a POST method handler to the `/api/transactions` endpoint in the backend.

## Task 3: Update Navigation on All Pages

Add this link to the nav-links section in all template files:
- templates/dashboard.html
- templates/holdings.html
- templates/transactions.html
- templates/dividends.html

```html
<a href="/money-invested">Money Invested</a>
```

**Important**: Also add the link to the newly created money_invested.html (already done).

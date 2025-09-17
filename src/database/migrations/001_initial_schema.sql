-- Inventory Management System - Initial Schema
-- Created: 2025-09-17
-- Description: Core tables for inventory management

-- Enable UUID extension for better primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Categories table for product categorization
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parent_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Suppliers table
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100) DEFAULT 'Japan',
    postal_code VARCHAR(20),
    tax_id VARCHAR(50),
    payment_terms INTEGER DEFAULT 30, -- days
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku VARCHAR(50) NOT NULL UNIQUE, -- Stock Keeping Unit
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    barcode VARCHAR(100),
    unit_of_measure VARCHAR(20) DEFAULT 'pcs', -- pieces, kg, liters, etc.
    unit_cost DECIMAL(12, 2),
    selling_price DECIMAL(12, 2),
    minimum_stock INTEGER DEFAULT 0,
    maximum_stock INTEGER,
    reorder_point INTEGER DEFAULT 0,
    weight DECIMAL(8, 3), -- in kg
    dimensions VARCHAR(50), -- e.g., "20x15x10 cm"
    shelf_location VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Inventory table for current stock levels
CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    location VARCHAR(100) DEFAULT 'Main Warehouse',
    quantity_on_hand INTEGER NOT NULL DEFAULT 0,
    quantity_reserved INTEGER DEFAULT 0, -- for orders not yet shipped
    quantity_available INTEGER GENERATED ALWAYS AS (quantity_on_hand - quantity_reserved) STORED,
    last_counted_at TIMESTAMP WITH TIME ZONE,
    last_movement_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one inventory record per product per location
    UNIQUE(product_id, location)
);

-- Transaction types enum
CREATE TYPE transaction_type AS ENUM (
    'purchase',      -- incoming stock from supplier
    'sale',          -- outgoing stock to customer
    'adjustment',    -- manual stock adjustment
    'transfer',      -- transfer between locations
    'return',        -- customer return
    'damaged',       -- damaged goods removal
    'expired',       -- expired goods removal
    'stocktake'      -- physical count adjustment
);

-- Transactions table for all inventory movements
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    type transaction_type NOT NULL,
    quantity INTEGER NOT NULL, -- positive for inbound, negative for outbound
    unit_cost DECIMAL(12, 2),
    total_cost DECIMAL(12, 2) GENERATED ALWAYS AS (ABS(quantity) * COALESCE(unit_cost, 0)) STORED,
    reference_number VARCHAR(100), -- PO number, invoice number, etc.
    location VARCHAR(100) DEFAULT 'Main Warehouse',
    notes TEXT,
    performed_by VARCHAR(100) DEFAULT 'System',
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX idx_categories_parent_id ON categories(parent_id);
CREATE INDEX idx_categories_name ON categories(name);
CREATE INDEX idx_suppliers_name ON suppliers(name);
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_supplier_id ON products(supplier_id);
CREATE INDEX idx_inventory_product_id ON inventory(product_id);
CREATE INDEX idx_inventory_location ON inventory(location);
CREATE INDEX idx_transactions_product_id ON transactions(product_id);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_performed_at ON transactions(performed_at);
CREATE INDEX idx_transactions_reference_number ON transactions(reference_number);

-- Triggers for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_categories_updated_at 
    BEFORE UPDATE ON categories 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_suppliers_updated_at 
    BEFORE UPDATE ON suppliers 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at 
    BEFORE UPDATE ON products 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_inventory_updated_at 
    BEFORE UPDATE ON inventory 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger to automatically update inventory when transactions occur
CREATE OR REPLACE FUNCTION update_inventory_on_transaction()
RETURNS TRIGGER AS $$
BEGIN
    -- Update or insert inventory record
    INSERT INTO inventory (product_id, location, quantity_on_hand, last_movement_at)
    VALUES (NEW.product_id, NEW.location, NEW.quantity, NEW.performed_at)
    ON CONFLICT (product_id, location)
    DO UPDATE SET
        quantity_on_hand = inventory.quantity_on_hand + NEW.quantity,
        last_movement_at = NEW.performed_at,
        updated_at = CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER inventory_update_trigger
    AFTER INSERT ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_inventory_on_transaction();

-- Views for common queries
CREATE VIEW low_stock_products AS
SELECT 
    p.id,
    p.sku,
    p.name,
    c.name as category_name,
    i.quantity_available,
    p.reorder_point,
    p.minimum_stock,
    s.name as supplier_name
FROM products p
JOIN categories c ON p.category_id = c.id
LEFT JOIN suppliers s ON p.supplier_id = s.id
LEFT JOIN inventory i ON p.id = i.product_id
WHERE p.is_active = TRUE 
    AND (i.quantity_available <= p.reorder_point OR i.quantity_available IS NULL)
ORDER BY COALESCE(i.quantity_available, 0) ASC;

CREATE VIEW inventory_summary AS
SELECT 
    p.id as product_id,
    p.sku,
    p.name as product_name,
    c.name as category_name,
    s.name as supplier_name,
    i.location,
    COALESCE(i.quantity_on_hand, 0) as quantity_on_hand,
    COALESCE(i.quantity_reserved, 0) as quantity_reserved,
    COALESCE(i.quantity_available, 0) as quantity_available,
    p.unit_cost,
    p.selling_price,
    (COALESCE(i.quantity_available, 0) * COALESCE(p.selling_price, 0)) as total_value,
    i.last_movement_at
FROM products p
JOIN categories c ON p.category_id = c.id
LEFT JOIN suppliers s ON p.supplier_id = s.id
LEFT JOIN inventory i ON p.id = i.product_id
WHERE p.is_active = TRUE
ORDER BY p.name;

-- Comments for documentation
COMMENT ON TABLE categories IS 'Product categories with hierarchical support';
COMMENT ON TABLE suppliers IS 'Supplier information and contact details';
COMMENT ON TABLE products IS 'Product master data';
COMMENT ON TABLE inventory IS 'Current stock levels by location';
COMMENT ON TABLE transactions IS 'All inventory movements and changes';

COMMENT ON COLUMN products.sku IS 'Stock Keeping Unit - unique product identifier';
COMMENT ON COLUMN products.reorder_point IS 'Quantity level that triggers reorder';
COMMENT ON COLUMN inventory.quantity_reserved IS 'Quantity allocated but not yet shipped';
COMMENT ON COLUMN transactions.quantity IS 'Positive for inbound, negative for outbound';

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO inventory_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO inventory_user;
-- ============================================================
-- UniTrade Improved Database Setup Script
-- ============================================================

CREATE DATABASE IF NOT EXISTS unitrade_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE unitrade_db;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    username     VARCHAR(50)  UNIQUE NOT NULL,
    email        VARCHAR(100) UNIQUE NOT NULL,
    password     VARCHAR(255) NOT NULL,
    first_name   VARCHAR(50)  NOT NULL,
    last_name    VARCHAR(50)  NOT NULL,
    university   VARCHAR(100) DEFAULT '',
    student_id   VARCHAR(50)  DEFAULT '',
    phone        VARCHAR(20)  DEFAULT '',
    bio          TEXT         DEFAULT NULL,
    profile_pic  VARCHAR(255) DEFAULT NULL,
    avg_rating   DECIMAL(3,2) DEFAULT 0.00,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email    (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- ITEMS
-- ============================================================
CREATE TABLE IF NOT EXISTS items (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    title          VARCHAR(100) NOT NULL,
    description    TEXT,
    category       VARCHAR(50),
    price          DECIMAL(10,2) NOT NULL,
    item_condition VARCHAR(20),
    image_url      VARCHAR(255) DEFAULT 'uploads/items/placeholder.jpg',
    seller_id      INT NOT NULL,
    status         ENUM('available','pending','sold') DEFAULT 'available',
    views          INT DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_seller   (seller_id),
    INDEX idx_status   (status),
    INDEX idx_category (category),
    FULLTEXT INDEX idx_search (title, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TRANSACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    item_id          INT NOT NULL,
    buyer_id         INT NOT NULL,
    seller_id        INT NOT NULL,
    price            DECIMAL(10,2) NOT NULL,
    meeting_location VARCHAR(200) DEFAULT '',
    pickup_location  VARCHAR(200) DEFAULT '',
    meeting_time     DATETIME,
    status           ENUM('pending','accepted','completed','cancelled') DEFAULT 'pending',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id)   REFERENCES items(id)  ON DELETE CASCADE,
    FOREIGN KEY (buyer_id)  REFERENCES users(id)  ON DELETE CASCADE,
    FOREIGN KEY (seller_id) REFERENCES users(id)  ON DELETE CASCADE,
    INDEX idx_buyer  (buyer_id),
    INDEX idx_seller (seller_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- REVIEWS  (one per transaction direction)
-- ============================================================
CREATE TABLE IF NOT EXISTS reviews (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT NOT NULL,
    reviewer_id    INT NOT NULL,
    reviewee_id    INT NOT NULL,
    rating         TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment        TEXT DEFAULT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_review (transaction_id, reviewer_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id)    REFERENCES users(id)        ON DELETE CASCADE,
    FOREIGN KEY (reviewee_id)    REFERENCES users(id)        ON DELETE CASCADE,
    INDEX idx_reviewee (reviewee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- WISHLIST
-- ============================================================
CREATE TABLE IF NOT EXISTS wishlist (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL,
    item_id    INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wish (user_id, item_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL,
    message    VARCHAR(500) NOT NULL,
    link       VARCHAR(255) DEFAULT NULL,
    is_read    TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_unread (user_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'UniTrade DB setup complete!' AS status;

"""50 benchmark questions with hand-written gold SQL (SQLite) for the Olist database.

difficulty: easy = one table, medium = joins / grouping, hard = dates, CTEs, window functions.
"""

QUESTIONS = [
    # ------------------------------------------------------------------ easy
    ("easy", "How many orders are in the database?",
     "SELECT COUNT(*) AS order_count FROM orders"),
    ("easy", "How many unique customers are there?",
     "SELECT COUNT(DISTINCT customer_unique_id) AS customers FROM customers"),
    ("easy", "How many sellers are on the platform?",
     "SELECT COUNT(*) AS sellers FROM sellers"),
    ("easy", "How many orders are there for each order status?",
     "SELECT order_status, COUNT(*) AS order_count FROM orders GROUP BY order_status ORDER BY order_count DESC"),
    ("easy", "What is the average review score?",
     "SELECT ROUND(AVG(review_score), 2) AS avg_review_score FROM reviews"),
    ("easy", "How many reviews were given for each review score?",
     "SELECT review_score, COUNT(*) AS reviews FROM reviews GROUP BY review_score ORDER BY review_score"),
    ("easy", "Which payment types are used and how many payments use each?",
     "SELECT payment_type, COUNT(*) AS payments FROM payments GROUP BY payment_type ORDER BY payments DESC"),
    ("easy", "What is the total payment value across all payments?",
     "SELECT ROUND(SUM(payment_value), 2) AS total_payment_value FROM payments"),
    ("easy", "What is the average item price?",
     "SELECT ROUND(AVG(price), 2) AS avg_price FROM order_items"),
    ("easy", "What is the most expensive item price ever sold?",
     "SELECT MAX(price) AS max_price FROM order_items"),
    ("easy", "Which 5 states have the most customers?",
     "SELECT customer_state, COUNT(DISTINCT customer_unique_id) AS customers FROM customers "
     "GROUP BY customer_state ORDER BY customers DESC LIMIT 5"),
    ("easy", "How many sellers are in each state?",
     "SELECT seller_state, COUNT(*) AS sellers FROM sellers GROUP BY seller_state ORDER BY sellers DESC"),
    ("easy", "How many products are there in each category (English names)?",
     "SELECT category_english, COUNT(*) AS products FROM products GROUP BY category_english ORDER BY products DESC"),
    ("easy", "What is the average number of payment installments?",
     "SELECT ROUND(AVG(payment_installments), 2) AS avg_installments FROM payments"),
    ("easy", "What is the average freight value per item?",
     "SELECT ROUND(AVG(freight_value), 2) AS avg_freight FROM order_items"),
    ("easy", "How many orders were canceled?",
     "SELECT COUNT(*) AS canceled_orders FROM orders WHERE order_status = 'canceled'"),

    # ---------------------------------------------------------------- medium
    ("medium", "What is the total revenue by product category? Show the top 10.",
     "SELECT p.category_english, ROUND(SUM(oi.price), 2) AS revenue FROM order_items oi "
     "JOIN products p ON p.product_id = oi.product_id GROUP BY p.category_english ORDER BY revenue DESC LIMIT 10"),
    ("medium", "Which 10 sellers generated the most revenue?",
     "SELECT seller_id, ROUND(SUM(price), 2) AS revenue FROM order_items GROUP BY seller_id ORDER BY revenue DESC LIMIT 10"),
    ("medium", "What is the average review score by product category?",
     "SELECT p.category_english, ROUND(AVG(r.review_score), 2) AS avg_score FROM reviews r "
     "JOIN order_items oi ON oi.order_id = r.order_id JOIN products p ON p.product_id = oi.product_id "
     "GROUP BY p.category_english ORDER BY avg_score DESC"),
    ("medium", "What is the total revenue by customer state?",
     "SELECT c.customer_state, ROUND(SUM(oi.price), 2) AS revenue FROM order_items oi "
     "JOIN orders o ON o.order_id = oi.order_id JOIN customers c ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_state ORDER BY revenue DESC"),
    ("medium", "What is the average order value (sum of item prices per order)?",
     "SELECT ROUND(AVG(order_total), 2) AS avg_order_value FROM "
     "(SELECT order_id, SUM(price) AS order_total FROM order_items GROUP BY order_id)"),
    ("medium", "How many items does an order contain on average?",
     "SELECT ROUND(AVG(n), 2) AS avg_items_per_order FROM (SELECT order_id, COUNT(*) AS n FROM order_items GROUP BY order_id)"),
    ("medium", "Which 5 product categories sold the most items?",
     "SELECT p.category_english, COUNT(*) AS items_sold FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
     "GROUP BY p.category_english ORDER BY items_sold DESC LIMIT 5"),
    ("medium", "What is the total freight cost by seller state?",
     "SELECT s.seller_state, ROUND(SUM(oi.freight_value), 2) AS total_freight FROM order_items oi "
     "JOIN sellers s ON s.seller_id = oi.seller_id GROUP BY s.seller_state ORDER BY total_freight DESC"),
    ("medium", "What is the average payment value for each payment type?",
     "SELECT payment_type, ROUND(AVG(payment_value), 2) AS avg_payment FROM payments GROUP BY payment_type ORDER BY avg_payment DESC"),
    ("medium", "How many orders did each customer state place? Show the top 10.",
     "SELECT c.customer_state, COUNT(*) AS orders FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_state ORDER BY orders DESC LIMIT 10"),
    ("medium", "Which 5 cities have the most customers?",
     "SELECT customer_city, COUNT(DISTINCT customer_unique_id) AS customers FROM customers "
     "GROUP BY customer_city ORDER BY customers DESC LIMIT 5"),
    ("medium", "What share of orders received a 5-star review? Give a percentage.",
     "SELECT ROUND(100.0 * SUM(review_score = 5) / COUNT(*), 2) AS pct_five_star FROM reviews"),
    ("medium", "What is the average product weight in grams by category?",
     "SELECT category_english, ROUND(AVG(product_weight_g), 2) AS avg_weight_g FROM products "
     "GROUP BY category_english ORDER BY avg_weight_g DESC"),
    ("medium", "How many sellers sold at least one item in each product category?",
     "SELECT p.category_english, COUNT(DISTINCT oi.seller_id) AS sellers FROM order_items oi "
     "JOIN products p ON p.product_id = oi.product_id GROUP BY p.category_english ORDER BY sellers DESC"),
    ("medium", "What is the average review score for each customer state?",
     "SELECT c.customer_state, ROUND(AVG(r.review_score), 2) AS avg_score FROM reviews r "
     "JOIN orders o ON o.order_id = r.order_id JOIN customers c ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_state ORDER BY avg_score DESC"),
    ("medium", "Which 10 products were sold the most times?",
     "SELECT product_id, COUNT(*) AS times_sold FROM order_items GROUP BY product_id ORDER BY times_sold DESC LIMIT 10"),
    ("medium", "What percentage of payments are made by credit card?",
     "SELECT ROUND(100.0 * SUM(payment_type = 'credit_card') / COUNT(*), 2) AS pct_credit_card FROM payments"),
    ("medium", "What is the total revenue from delivered orders only?",
     "SELECT ROUND(SUM(oi.price), 2) AS delivered_revenue FROM order_items oi "
     "JOIN orders o ON o.order_id = oi.order_id WHERE o.order_status = 'delivered'"),

    # ------------------------------------------------------------------ hard
    ("hard", "How many orders were placed each month?",
     "SELECT strftime('%Y-%m', order_purchase_timestamp) AS month, COUNT(*) AS orders FROM orders GROUP BY month ORDER BY month"),
    ("hard", "What was the total revenue per month?",
     "SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month, ROUND(SUM(oi.price), 2) AS revenue "
     "FROM orders o JOIN order_items oi ON oi.order_id = o.order_id GROUP BY month ORDER BY month"),
    ("hard", "What is the average delivery time in days for delivered orders?",
     "SELECT ROUND(AVG(julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)), 2) AS avg_delivery_days "
     "FROM orders WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL"),
    ("hard", "What percentage of delivered orders arrived later than the estimated delivery date?",
     "SELECT ROUND(100.0 * SUM(order_delivered_customer_date > order_estimated_delivery_date) / COUNT(*), 2) AS pct_late "
     "FROM orders WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL"),
    ("hard", "Do late deliveries get lower review scores? Compare the average score for late vs on-time deliveries.",
     "SELECT CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'late' ELSE 'on_time' END AS delivery, "
     "ROUND(AVG(r.review_score), 2) AS avg_score FROM orders o JOIN reviews r ON r.order_id = o.order_id "
     "WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL GROUP BY delivery"),
    ("hard", "What is the average delivery time in days for each customer state?",
     "SELECT c.customer_state, ROUND(AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)), 2) AS avg_days "
     "FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
     "WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL "
     "GROUP BY c.customer_state ORDER BY avg_days DESC"),
    ("hard", "How many customers placed more than one order?",
     "SELECT COUNT(*) AS repeat_customers FROM (SELECT c.customer_unique_id FROM orders o "
     "JOIN customers c ON c.customer_id = o.customer_id GROUP BY c.customer_unique_id HAVING COUNT(DISTINCT o.order_id) > 1)"),
    ("hard", "Which weekday has the most orders?",
     "SELECT CASE strftime('%w', order_purchase_timestamp) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' "
     "WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' ELSE 'Saturday' END AS weekday, "
     "COUNT(*) AS orders FROM orders GROUP BY weekday ORDER BY orders DESC LIMIT 1"),
    ("hard", "How many orders are placed at each hour of the day?",
     "SELECT CAST(strftime('%H', order_purchase_timestamp) AS INTEGER) AS hour, COUNT(*) AS orders FROM orders GROUP BY hour ORDER BY hour"),
    ("hard", "What was the month-over-month revenue growth percentage?",
     "WITH m AS (SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month, SUM(oi.price) AS revenue "
     "FROM orders o JOIN order_items oi ON oi.order_id = o.order_id GROUP BY month) "
     "SELECT month, ROUND(revenue, 2) AS revenue, ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month)) / "
     "LAG(revenue) OVER (ORDER BY month), 2) AS growth_pct FROM m ORDER BY month"),
    ("hard", "For each product category, what is its share of total revenue in percent? Top 10.",
     "SELECT p.category_english, ROUND(100.0 * SUM(oi.price) / (SELECT SUM(price) FROM order_items), 2) AS revenue_share_pct "
     "FROM order_items oi JOIN products p ON p.product_id = oi.product_id GROUP BY p.category_english "
     "ORDER BY revenue_share_pct DESC LIMIT 10"),
    ("hard", "What is the cumulative revenue by month?",
     "WITH m AS (SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month, SUM(oi.price) AS revenue "
     "FROM orders o JOIN order_items oi ON oi.order_id = o.order_id GROUP BY month) "
     "SELECT month, ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS cumulative_revenue FROM m ORDER BY month"),
    ("hard", "Which seller has the highest average review score among sellers with at least 10 reviewed items?",
     "SELECT oi.seller_id, ROUND(AVG(r.review_score), 2) AS avg_score FROM order_items oi "
     "JOIN reviews r ON r.order_id = oi.order_id GROUP BY oi.seller_id HAVING COUNT(*) >= 10 "
     "ORDER BY avg_score DESC LIMIT 1"),
    ("hard", "What is the best-selling category by revenue in each customer state?",
     "WITH s AS (SELECT c.customer_state, p.category_english, SUM(oi.price) AS revenue FROM order_items oi "
     "JOIN orders o ON o.order_id = oi.order_id JOIN customers c ON c.customer_id = o.customer_id "
     "JOIN products p ON p.product_id = oi.product_id GROUP BY c.customer_state, p.category_english), "
     "r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_state ORDER BY revenue DESC) AS rn FROM s) "
     "SELECT customer_state, category_english, ROUND(revenue, 2) AS revenue FROM r WHERE rn = 1 ORDER BY customer_state"),
    ("hard", "What is the average number of days between purchase and order approval?",
     "SELECT ROUND(AVG(julianday(order_approved_at) - julianday(order_purchase_timestamp)), 2) AS avg_approval_days "
     "FROM orders WHERE order_approved_at IS NOT NULL"),
    ("hard", "Which year had the highest total revenue?",
     "SELECT strftime('%Y', o.order_purchase_timestamp) AS year, ROUND(SUM(oi.price), 2) AS revenue FROM orders o "
     "JOIN order_items oi ON oi.order_id = o.order_id GROUP BY year ORDER BY revenue DESC LIMIT 1"),
]

assert len(QUESTIONS) == 50, len(QUESTIONS)

INSERT OR IGNORE INTO admins (username, password_hash, display_name)
VALUES (
    'admin',
    'pbkdf2_sha256$200000$library_admin_seed$zTKFgXr3eUBlID3MojccV48dD2eNyRyrrPWLAfpomd4=',
    '系统管理员'
);

INSERT OR IGNORE INTO books
(isbn, title, author, publisher, category, published_year, total_count, available_count, location, status)
VALUES
('9787111128069', '软件工程：实践者的研究方法', 'Roger S. Pressman', '机械工业出版社', '软件工程', 2021, 5, 3, 'A区-01-01', 'active'),
('9787115428028', '数据库系统概念', 'Abraham Silberschatz', '机械工业出版社', '数据库', 2020, 4, 3, 'A区-02-04', 'active'),
('9787111213826', '计算机网络：自顶向下方法', 'James F. Kurose', '机械工业出版社', '计算机网络', 2022, 3, 3, 'B区-03-02', 'active'),
('9787302423287', 'Python 编程：从入门到实践', 'Eric Matthes', '人民邮电出版社', '编程语言', 2023, 6, 5, 'C区-01-05', 'active'),
('9787115546081', '算法导论', 'Thomas H. Cormen', '机械工业出版社', '算法', 2022, 2, 2, 'B区-01-03', 'active');

INSERT OR IGNORE INTO readers
(card_no, name, phone, email, department, status)
VALUES
('R2026001', '张三', '13800000001', 'zhangsan@example.com', '软件工程 1 班', 'active'),
('R2026002', '李四', '13800000002', 'lisi@example.com', '计算机科学 2 班', 'active'),
('R2026003', '王五', '13800000003', 'wangwu@example.com', '信息管理 1 班', 'active'),
('R2026004', '赵六', '13800000004', 'zhaoliu@example.com', '网络工程 3 班', 'suspended');

INSERT OR IGNORE INTO loans
(book_id, reader_id, loan_date, due_date, return_date, status, note)
SELECT b.id, r.id, date('now', '-10 day'), date('now', '+20 day'), NULL, 'borrowed', '正常借阅样例'
FROM books b, readers r
WHERE b.isbn = '9787111128069'
  AND r.card_no = 'R2026001'
  AND NOT EXISTS (SELECT 1 FROM loans WHERE note = '正常借阅样例');

INSERT OR IGNORE INTO loans
(book_id, reader_id, loan_date, due_date, return_date, status, note)
SELECT b.id, r.id, date('now', '-40 day'), date('now', '-10 day'), NULL, 'borrowed', '逾期未还样例'
FROM books b, readers r
WHERE b.isbn = '9787111128069'
  AND r.card_no = 'R2026002'
  AND NOT EXISTS (SELECT 1 FROM loans WHERE note = '逾期未还样例');

INSERT OR IGNORE INTO loans
(book_id, reader_id, loan_date, due_date, return_date, status, note)
SELECT b.id, r.id, date('now', '-20 day'), date('now', '+10 day'), date('now', '-2 day'), 'returned', '已归还样例'
FROM books b, readers r
WHERE b.isbn = '9787115428028'
  AND r.card_no = 'R2026003'
  AND NOT EXISTS (SELECT 1 FROM loans WHERE note = '已归还样例');

INSERT OR IGNORE INTO loans
(book_id, reader_id, loan_date, due_date, return_date, status, note)
SELECT b.id, r.id, date('now', '-3 day'), date('now', '+27 day'), NULL, 'borrowed', '数据库课程参考书'
FROM books b, readers r
WHERE b.isbn = '9787115428028'
  AND r.card_no = 'R2026001'
  AND NOT EXISTS (SELECT 1 FROM loans WHERE note = '数据库课程参考书');


from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
import uuid
from datetime import datetime
import pandas as pd
from io import BytesIO
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50* 1024 * 1024  # 50MB max file size

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# 配置日志
def setup_logging():
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler = RotatingFileHandler('logs/app.log', maxBytes=10*1024*1024, backupCount=5)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

# 初始化日志
setup_logging()

# 日志记录装饰器
def log_operation(operation_type):
    def decorator(f):
        def wrapper(*args, **kwargs):
            user = session.get('admin_username', 'anonymous')
            # 构建操作详情
            details = f"操作: {operation_type}, 用户: {user}, URL: {request.url}"
            if kwargs.get('app_number'):
                details += f", 申请编号: {kwargs['app_number']}"
            elif kwargs.get('filename'):
                details += f", 文件名: {kwargs['filename']}"
            if request.method == 'POST':
                form_data = {k: '***' if k == 'password' else v for k, v in request.form.items()}
                details += f", 表单数据: {form_data}"
            if request.args:
                details += f", 查询参数: {dict(request.args)}"
            
            try:
                result = f(*args, **kwargs)
                app.logger.info(f"{details}, 结果: 成功")
                return result
            except Exception as e:
                app.logger.error(f"{details}, 结果: 失败, 错误: {str(e)}", exc_info=True)
                raise
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# 数据库初始化
def init_db():
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_number TEXT UNIQUE NOT NULL,
            purchaser TEXT NOT NULL,
            purchase_details TEXT,
            item_name TEXT NOT NULL,
            product_link TEXT,
            usage_type TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_time DATE NOT NULL,
            invoice_number TEXT NOT NULL,
            invoice_amount REAL NOT NULL,
            invoice_date DATE NOT NULL,
            status TEXT DEFAULT '待审批',
            approval_comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_number TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY (app_number) REFERENCES applications (app_number)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )''')
        admin_hash = generate_password_hash('admin123')
        c.execute('INSERT OR IGNORE INTO admins (username, password_hash) VALUES (?, ?)', 
                  ('admin', admin_hash))
        conn.commit()

# 生成申请编号
def generate_app_number():
    return f"FB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4().hex[:6]).upper()}"

# 首页 - 申请表单
@app.route('/')
@log_operation('访问申请表单页面')
def index():
    return render_template('index.html')

# 处理申请提交
@app.route('/submit', methods=['POST'])
@log_operation('提交报销申请')
def submit_application():
    app_number = generate_app_number()
    data = {
        'app_number': app_number,
        'purchaser': request.form['purchaser'],
        'purchase_details': request.form['purchase_details'],
        'item_name': request.form['item_name'],
        'product_link': request.form['product_link'],
        'usage_type': request.form['usage_type'],
        'item_type': request.form['item_type'],
        'quantity': int(request.form['quantity']),
        'purchase_time': request.form['purchase_time'],
        'invoice_number': request.form['invoice_number'],
        'invoice_amount': float(request.form['invoice_amount']),
        'invoice_date': request.form['invoice_date']
    }
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO applications 
                     (app_number, purchaser, purchase_details, item_name, product_link, 
                      usage_type, item_type, quantity, purchase_time, invoice_number, 
                      invoice_amount, invoice_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (data['app_number'], data['purchaser'], data['purchase_details'], 
                   data['item_name'], data['product_link'], data['usage_type'], 
                   data['item_type'], data['quantity'], data['purchase_time'], 
                   data['invoice_number'], data['invoice_amount'], data['invoice_date']))
        
        files = request.files.getlist('attachments')
        uploaded_files = []
        for file in files:
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1]
                base_filename = f"{data['invoice_number']}{ext}"
                new_filename = base_filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                
                counter = 1
                while os.path.exists(filepath):
                    new_filename = f"{data['invoice_number']}_{counter}{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    counter += 1
                
                file.save(filepath)
                uploaded_files.append(new_filename)
                
                c.execute('''INSERT INTO attachments 
                             (app_number, original_filename, stored_filename, file_path)
                             VALUES (?, ?, ?, ?)''',
                          (app_number, file.filename, new_filename, filepath))
        
        conn.commit()
    
    return redirect(url_for('success', app_number=app_number))

# 提交成功页面
@app.route('/success/<app_number>')
@log_operation('查看申请结果')
def success(app_number):
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM applications WHERE app_number = ?', (app_number,))
        application = c.fetchone()
    
    if not application:
        flash('申请不存在')
        return redirect(url_for('index'))
    
    return render_template('success.html', app_number=app_number, status=application[13])

# 管理员登录页面
@app.route('/admin/login')
@log_operation('访问管理员登录页面')
def admin_login():
    return render_template('admin_login.html')

# 处理管理员登录
@app.route('/admin/auth', methods=['POST'])
@log_operation('管理员登录验证')
def admin_auth():
    username = request.form['username']
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT password_hash FROM admins WHERE username = ?', (username,))
        result = c.fetchone()
    
    if result and check_password_hash(result[0], request.form['password']):
        session['admin_logged_in'] = True
        session['admin_username'] = username
        return redirect(url_for('admin_dashboard'))
    else:
        flash('用户名或密码错误')
        return redirect(url_for('admin_login'))

# 管理员后台
@app.route('/admin/dashboard')
@log_operation('访问管理后台')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash('请先登录')
        return redirect(url_for('admin_login'))
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        search_purchaser = request.args.get('purchaser', '')
        search_status = request.args.get('status', '')
        search_usage = request.args.get('usage', '')
        sort_field = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        
        sortable_fields = {
            'created_at': 'created_at',
            'purchaser': 'purchaser',
            'item_name': 'item_name',
            'invoice_amount': 'invoice_amount',
            'invoice_number': 'invoice_number',
            'invoice_date': 'invoice_date',
            'purchase_time': 'purchase_time',
            'item_type': 'item_type',
            'status': 'status'
        }
        
        if sort_field not in sortable_fields:
            sort_field = 'created_at'
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'
        
        query = 'SELECT * FROM applications WHERE 1=1'
        params = []
        if search_purchaser:
            query += ' AND purchaser LIKE ?'
            params.append(f'%{search_purchaser}%')
        if search_status:
            query += ' AND status = ?'
            params.append(search_status)
        if search_usage:
            query += ' AND usage_type = ?'
            params.append(search_usage)
        
        query += f' ORDER BY {sortable_fields[sort_field]} {sort_order.upper()}'
        c.execute(query, params)
        applications = c.fetchall()
    
    return render_template('admin_dashboard.html', applications=applications)

# 申请详情和审批
@app.route('/admin/application/<app_number>')
@log_operation('查看申请详情')
def admin_application_detail(app_number):
    if not session.get('admin_logged_in'):
        flash('请先登录')
        return redirect(url_for('admin_login'))
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM applications WHERE app_number = ?', (app_number,))
        application = c.fetchone()
        c.execute('SELECT * FROM attachments WHERE app_number = ?', (app_number,))
        attachments = c.fetchall()
    
    if not application:
        flash('申请不存在')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_detail.html', application=application, attachments=attachments)

# 处理审批
@app.route('/admin/approve/<app_number>', methods=['POST'])
@log_operation('审批申请')
def approve_application(app_number):
    if not session.get('admin_logged_in'):
        flash('请先登录')
        return redirect(url_for('admin_login'))
    
    status = request.form['status']
    comment = request.form.get('comment', '')
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('UPDATE applications SET status = ?, approval_comment = ?, updated_at = CURRENT_TIMESTAMP WHERE app_number = ?',
                  (status, comment, app_number))
        conn.commit()
    
    flash('审批完成')
    return redirect(url_for('admin_application_detail', app_number=app_number))

# 导出Excel
@app.route('/admin/export')
@log_operation('导出Excel数据')
def export_excel():
    if not session.get('admin_logged_in'):
        flash('请先登录')
        return redirect(url_for('admin_login'))
    
    with sqlite3.connect('reimbursement.db') as conn:
        df = pd.read_sql_query('SELECT * FROM applications ORDER BY created_at DESC', conn)
    
    df.columns = ['ID', '申请编号', '购买人', '商品参数及用途说明', '物品名称', '商品链接', '使用途径', 
                  '物品类型', '数量', '购买时间', '发票号码', '发票金额', '开票日期', 
                  '状态', '审批意见', '创建时间', '更新时间']
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='报销申请', index=False)
    
    output.seek(0)
    filename = f'报销申请_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
    return send_file(output, 
                     download_name=filename, 
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# 下载附件
@app.route('/download/<filename>')
@log_operation('下载附件')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash('文件不存在')
        return redirect(url_for('admin_dashboard'))
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT app_number, original_filename FROM attachments WHERE stored_filename = ?', (filename,))
        attachment_info = c.fetchone()
    
    return send_file(file_path)

# 管理员退出
@app.route('/admin/logout')
@log_operation('管理员退出')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.logger.info("系统启动 - 数据库初始化完成, 服务器启动在 http://0.0.0.0:5000, 日志文件: logs/app.log")
    app.run(debug=True, host='0.0.0.0', port=5000)
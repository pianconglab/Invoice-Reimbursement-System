from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
import uuid
from datetime import datetime, timezone, timedelta
import pandas as pd
from io import BytesIO
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

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

# 获取北京时间
def get_beijing_time():
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime('%Y-%m-%d %H:%M:%S')

# 生成申请编号
def generate_app_number():
    return f"FB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4().hex[:6]).upper()}"

# 首页 - 申请表单
@app.route('/')
@log_operation('访问申请表单页面')
def index():
    return render_template('index.html')

# 查询报销状态页面
@app.route('/query_status', methods=['GET', 'POST'])
@log_operation('查询申请状态')
def query_status():
    query_result = None
    
    if request.method == 'POST':
        invoice_number = request.form['query_invoice_number'].strip()
        
        if invoice_number:
            with sqlite3.connect('reimbursement.db') as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM applications WHERE invoice_number = ?', (invoice_number,))
                application = c.fetchone()
            
            if application:
                # 将查询结果转换为字典格式以便在模板中使用
                columns = ['id', 'app_number', 'purchaser', 'purchase_details', 'item_name', 
                          'product_link', 'usage_type', 'item_type', 'quantity', 'purchase_time', 
                          'invoice_number', 'invoice_amount', 'invoice_date', 'status', 
                          'approval_comment', 'created_at', 'updated_at']
                
                query_result = {columns[i]: application[i] for i in range(len(columns))}
            else:
                query_result = 'not_found'
    
    return render_template('query_status.html', query_result=query_result)

# 修改申请记录页面
@app.route('/edit_application', methods=['GET', 'POST'])
@log_operation('修改申请记录页面')
def edit_application_page():
    search_result = None
    attachments = []
    
    if request.method == 'POST':
        invoice_number = request.form['search_invoice_number'].strip()
        
        if invoice_number:
            with sqlite3.connect('reimbursement.db') as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM applications WHERE invoice_number = ?', (invoice_number,))
                application = c.fetchone()
            
            if application:
                # 将查询结果转换为字典格式以便在模板中使用
                columns = ['id', 'app_number', 'purchaser', 'purchase_details', 'item_name', 
                          'product_link', 'usage_type', 'item_type', 'quantity', 'purchase_time', 
                          'invoice_number', 'invoice_amount', 'invoice_date', 'status', 
                          'approval_comment', 'created_at', 'updated_at']
                
                search_result = {columns[i]: application[i] for i in range(len(columns))}
                
                # 查询附件信息
                c.execute('SELECT * FROM attachments WHERE app_number = ?', (application[1],))
                attachments = c.fetchall()
            else:
                search_result = 'not_found'
    
    return render_template('edit_application.html', search_result=search_result, attachments=attachments)

# 通过发票号码直接编辑申请记录
@app.route('/edit_application/<invoice_number>')
@log_operation('直接编辑申请记录')
def edit_application_with_invoice(invoice_number):
    search_result = None
    attachments = []
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM applications WHERE invoice_number = ?', (invoice_number,))
        application = c.fetchone()
    
    if application:
        # 将查询结果转换为字典格式以便在模板中使用
        columns = ['id', 'app_number', 'purchaser', 'purchase_details', 'item_name', 
                  'product_link', 'usage_type', 'item_type', 'quantity', 'purchase_time', 
                  'invoice_number', 'invoice_amount', 'invoice_date', 'status', 
                  'approval_comment', 'created_at', 'updated_at']
        
        search_result = {columns[i]: application[i] for i in range(len(columns))}
        
        # 查询附件信息
        c.execute('SELECT * FROM attachments WHERE app_number = ?', (application[1],))
        attachments = c.fetchall()
    else:
        flash('申请记录不存在')
    
    return render_template('edit_application.html', search_result=search_result, attachments=attachments)

# 更新申请记录
@app.route('/update', methods=['POST'])
@log_operation('更新申请记录')
def update_application():
    app_number = request.form['app_number']
    
    # 首先检查申请是否存在
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT status FROM applications WHERE app_number = ?', (app_number,))
        application = c.fetchone()
        
        if not application:
            flash('申请记录不存在')
            return redirect(url_for('index'))
        
        # 检查申请状态，只允许修改待审批或驳回的申请
        if application[0] not in ['待审批', '驳回']:
            flash('只能修改待审批或已驳回的申请记录')
            return redirect(url_for('index'))
        
        # 更新申请记录
        c.execute('''UPDATE applications SET 
                     purchaser = ?, purchase_details = ?, item_name = ?, product_link = ?, 
                     usage_type = ?, item_type = ?, quantity = ?, purchase_time = ?, 
                     invoice_number = ?, invoice_amount = ?, invoice_date = ?, 
                     updated_at = ?
                     WHERE app_number = ?''',
                  (request.form['purchaser'], request.form['purchase_details'], 
                   request.form['item_name'], request.form['product_link'], 
                   request.form['usage_type'], request.form['item_type'], 
                   int(request.form['quantity']), request.form['purchase_time'], 
                   request.form['invoice_number'], float(request.form['invoice_amount']), 
                   request.form['invoice_date'], get_beijing_time(), app_number))
        
        # 处理待删除的附件
        deleted_attachments = request.form.get('deleted_attachments', '')
        if deleted_attachments:
            deleted_ids = [int(id.strip()) for id in deleted_attachments.split(',') if id.strip()]
            for attachment_id in deleted_ids:
                # 获取附件信息
                c.execute('SELECT file_path FROM attachments WHERE id = ?', (attachment_id,))
                attachment = c.fetchone()
                if attachment:
                    file_path = attachment[0]
                    # 删除文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    # 删除数据库记录
                    c.execute('DELETE FROM attachments WHERE id = ?', (attachment_id,))
        
        # 处理新上传的附件
        files = request.files.getlist('new_attachments')
        uploaded_files = []
        for file in files:
            if file and file.filename:
                ext = os.path.splitext(file.filename)[1]
                base_filename = f"{request.form['invoice_number']}{ext}"
                new_filename = base_filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                
                counter = 1
                while os.path.exists(filepath):
                    new_filename = f"{request.form['invoice_number']}_{counter}{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    counter += 1
                
                file.save(filepath)
                uploaded_files.append(new_filename)
                
                c.execute('''INSERT INTO attachments 
                             (app_number, original_filename, stored_filename, file_path)
                             VALUES (?, ?, ?, ?)''',
                          (app_number, file.filename, new_filename, filepath))
        
        conn.commit()
    
    flash(f'申请记录 {app_number} 已成功更新')
    return redirect(url_for('edit_application_page'))

# 处理申请提交
@app.route('/submit', methods=['POST'])
@log_operation('提交报销申请')
def submit_application():
    # 检查发票号码是否已存在
    invoice_number = request.form['invoice_number']
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM applications WHERE invoice_number = ?', (invoice_number,))
        if c.fetchone()[0] > 0:
            flash(f'发票号码 {invoice_number} 已存在，请检查是否重复提交或使用其他发票号码')
            return redirect(url_for('index'))
    
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
        'invoice_number': invoice_number,
        'invoice_amount': float(request.form['invoice_amount']),
        'invoice_date': request.form['invoice_date']
    }
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO applications 
                     (app_number, purchaser, purchase_details, item_name, product_link, 
                      usage_type, item_type, quantity, purchase_time, invoice_number, 
                      invoice_amount, invoice_date, created_at, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (data['app_number'], data['purchaser'], data['purchase_details'], 
                   data['item_name'], data['product_link'], data['usage_type'], 
                   data['item_type'], data['quantity'], data['purchase_time'], 
                   data['invoice_number'], data['invoice_amount'], data['invoice_date'],
                   get_beijing_time(), get_beijing_time()))
        
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

# 检查发票号码是否存在的API
@app.route('/check_invoice/<invoice_number>')
def check_invoice_number(invoice_number):
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM applications WHERE invoice_number = ?', (invoice_number,))
        exists = c.fetchone()[0] > 0
    return {'exists': exists}

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
        purchase_date_start = request.args.get('purchase_date_start', '')
        purchase_date_end = request.args.get('purchase_date_end', '')
        invoice_date_start = request.args.get('invoice_date_start', '')
        invoice_date_end = request.args.get('invoice_date_end', '')
        sort_field = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        
        # 分页参数
        per_page = int(request.args.get('per_page', 50))
        if per_page not in [25, 50, 100]:
            per_page = 50
        page = int(request.args.get('page', 1))
        offset = (page - 1) * per_page
        
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
        
        # 构建查询条件
        query = 'SELECT * FROM applications WHERE 1=1'
        count_query = 'SELECT COUNT(*) FROM applications WHERE 1=1'
        params = []
        if search_purchaser:
            query += ' AND purchaser LIKE ?'
            count_query += ' AND purchaser LIKE ?'
            params.append(f'%{search_purchaser}%')
        if search_status:
            query += ' AND status = ?'
            count_query += ' AND status = ?'
            params.append(search_status)
        if search_usage:
            query += ' AND usage_type = ?'
            count_query += ' AND usage_type = ?'
            params.append(search_usage)
        if purchase_date_start:
            query += ' AND purchase_time >= ?'
            count_query += ' AND purchase_time >= ?'
            params.append(purchase_date_start)
        if purchase_date_end:
            query += ' AND purchase_time <= ?'
            count_query += ' AND purchase_time <= ?'
            params.append(purchase_date_end)
        if invoice_date_start:
            query += ' AND invoice_date >= ?'
            count_query += ' AND invoice_date >= ?'
            params.append(invoice_date_start)
        if invoice_date_end:
            query += ' AND invoice_date <= ?'
            count_query += ' AND invoice_date <= ?'
            params.append(invoice_date_end)
        
        # 获取总记录数
        c.execute(count_query, params)
        total_count = c.fetchone()[0]
        
        # 获取分页数据
        query += f' ORDER BY {sortable_fields[sort_field]} {sort_order.upper()} LIMIT ? OFFSET ?'
        c.execute(query, params + [per_page, offset])
        applications = c.fetchall()
        
        # 计算分页信息
        total_pages = (total_count + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
    
    return render_template('admin_dashboard.html', 
                         applications=applications,
                         page=page,
                         per_page=per_page,
                         total_count=total_count,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next)

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
        c.execute('UPDATE applications SET status = ?, approval_comment = ?, updated_at = ? WHERE app_number = ?',
                  (status, comment, get_beijing_time(), app_number))
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
        # 使用与admin_dashboard相同的筛选逻辑
        search_purchaser = request.args.get('purchaser', '')
        search_status = request.args.get('status', '')
        search_usage = request.args.get('usage', '')
        purchase_date_start = request.args.get('purchase_date_start', '')
        purchase_date_end = request.args.get('purchase_date_end', '')
        invoice_date_start = request.args.get('invoice_date_start', '')
        invoice_date_end = request.args.get('invoice_date_end', '')
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
        if purchase_date_start:
            query += ' AND purchase_time >= ?'
            params.append(purchase_date_start)
        if purchase_date_end:
            query += ' AND purchase_time <= ?'
            params.append(purchase_date_end)
        if invoice_date_start:
            query += ' AND invoice_date >= ?'
            params.append(invoice_date_start)
        if invoice_date_end:
            query += ' AND invoice_date <= ?'
            params.append(invoice_date_end)
        
        query += f' ORDER BY {sortable_fields[sort_field]} {sort_order.upper()}'
        
        df = pd.read_sql_query(query, conn, params=params)
    
    df.columns = ['ID', '申请编号', '购买人', '商品参数及用途说明', '物品名称', '商品链接', '使用途径', 
                  '物品类型', '数量', '购买时间', '发票号码', '发票金额', '开票日期', 
                  '状态', '审批意见', '创建时间', '更新时间']
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='报销申请', index=False)
    
    output.seek(0)
    
    # 根据筛选条件生成文件名
    filename_parts = ['报销申请']
    if search_purchaser:
        filename_parts.append(f'购买人_{search_purchaser}')
    if search_status:
        filename_parts.append(f'状态_{search_status}')
    if purchase_date_start or purchase_date_end:
        date_range = []
        if purchase_date_start:
            date_range.append(f'从{purchase_date_start}')
        if purchase_date_end:
            date_range.append(f'到{purchase_date_end}')
        filename_parts.append(f'购买日期_{"".join(date_range)}')
    
    filename = f'{"_".join(filename_parts)}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
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

    # 使用原始文件名作为下载文件名，如果没有则使用存储的文件名
    download_name = attachment_info[1] if attachment_info and attachment_info[1] else filename

    return send_file(file_path, as_attachment=True, download_name=download_name)



# 删除申请记录
@app.route('/admin/delete/<app_number>', methods=['POST'])
@log_operation('删除申请记录')
def delete_application(app_number):
    if not session.get('admin_logged_in'):
        flash('请先登录')
        return redirect(url_for('admin_login'))
    
    with sqlite3.connect('reimbursement.db') as conn:
        c = conn.cursor()
        
        # 先查询申请是否存在
        c.execute('SELECT * FROM applications WHERE app_number = ?', (app_number,))
        application = c.fetchone()
        
        if not application:
            flash('申请记录不存在')
            return redirect(url_for('admin_dashboard'))
        
        # 获取所有附件信息
        c.execute('SELECT file_path FROM attachments WHERE app_number = ?', (app_number,))
        attachments = c.fetchall()
        
        # 删除文件系统中的附件文件
        for attachment in attachments:
            file_path = attachment[0]
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    app.logger.warning(f"删除文件失败: {file_path}, 错误: {str(e)}")
        
        # 删除数据库中的附件记录
        c.execute('DELETE FROM attachments WHERE app_number = ?', (app_number,))
        
        # 删除申请记录
        c.execute('DELETE FROM applications WHERE app_number = ?', (app_number,))
        
        conn.commit()
    
    flash(f'申请记录 {app_number} 已成功删除')
    return redirect(url_for('admin_dashboard'))

# 管理员退出
@app.route('/admin/logout')
@log_operation('管理员退出')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.logger.info("系统启动 - 数据库初始化完成, 服务器启动在 http://0.0.0.0:5000, 日志文件: logs/app.log，数据库文件: reimbursement.db，上传文件目录: uploads")
    app.run(debug=True, host='0.0.0.0', port=5000)
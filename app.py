from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
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
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# 配置日志
def setup_logging():
    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 应用日志
    app_handler = RotatingFileHandler('logs/app.log', maxBytes=10*1024*1024, backupCount=5)
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)
    
    # 操作日志（用户和管理员操作）
    operation_handler = RotatingFileHandler('logs/operations.log', maxBytes=10*1024*1024, backupCount=5)
    operation_handler.setFormatter(formatter)
    operation_handler.setLevel(logging.INFO)
    
    # 错误日志
    error_handler = RotatingFileHandler('logs/errors.log', maxBytes=10*1024*1024, backupCount=5)
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 配置应用日志
    app.logger.addHandler(app_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.INFO)
    
    # 创建操作日志记录器
    operation_logger = logging.getLogger('operations')
    operation_logger.addHandler(operation_handler)
    operation_logger.setLevel(logging.INFO)
    
    return operation_logger

# 初始化日志
operation_logger = setup_logging()

# 日志记录装饰器
def log_operation(operation_type):
    def decorator(f):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent', '')
            
            # 记录请求开始
            log_data = {
                'operation': operation_type,
                'method': request.method,
                'url': request.url,
                'client_ip': client_ip,
                'user_agent': user_agent,
                'start_time': start_time.isoformat(),
                'user': session.get('admin_username', 'anonymous')
            }
            
            # 记录请求参数（敏感信息过滤）
            if request.method == 'POST':
                form_data = dict(request.form)
                # 过滤敏感信息
                if 'password' in form_data:
                    form_data['password'] = '***'
                log_data['form_data'] = form_data
            
            if request.args:
                log_data['query_params'] = dict(request.args)
                
            try:
                # 执行原函数
                result = f(*args, **kwargs)
                
                # 记录成功结果
                end_time = datetime.now()
                log_data.update({
                    'status': 'success',
                    'end_time': end_time.isoformat(),
                    'duration_ms': (end_time - start_time).total_seconds() * 1000,
                    'response_type': type(result).__name__
                })
                
                operation_logger.info(f"操作成功: {json.dumps(log_data, ensure_ascii=False)}")
                return result
                
            except Exception as e:
                # 记录错误
                end_time = datetime.now()
                log_data.update({
                    'status': 'error',
                    'error': str(e),
                    'end_time': end_time.isoformat(),
                    'duration_ms': (end_time - start_time).total_seconds() * 1000
                })
                
                operation_logger.error(f"操作失败: {json.dumps(log_data, ensure_ascii=False)}")
                app.logger.error(f"操作异常: {operation_type} - {str(e)}", exc_info=True)
                raise
                
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# 数据库初始化
def init_db():
    conn = sqlite3.connect('reimbursement.db')
    c = conn.cursor()
    
    # 创建申请表
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
    
    # 创建附件表
    c.execute('''CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_number TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        FOREIGN KEY (app_number) REFERENCES applications (app_number)
    )''')
    
    # 创建管理员表（默认创建一个管理员账户：admin/admin123）
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )''')
    
    # 插入默认管理员账户
    admin_hash = generate_password_hash('admin123')
    c.execute('INSERT OR IGNORE INTO admins (username, password_hash) VALUES (?, ?)', 
              ('admin', admin_hash))
    
    conn.commit()
    conn.close()

# 生成申请编号
def generate_app_number():
    return f"FB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4().hex[:6]).upper()}"

# 首页 - 申请表单
@app.route('/')
@log_operation('访问申请表单页面')
def index():
    app.logger.info("用户访问申请表单页面")
    return render_template('index.html')

# 处理申请提交
@app.route('/submit', methods=['POST'])
@log_operation('提交报销申请')
def submit_application():
    try:
        # 生成申请编号
        app_number = generate_app_number()
        
        # 获取表单数据
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
        
        app.logger.info(f"新申请提交 - 申请编号: {app_number}, 购买人: {data['purchaser']}, 物品: {data['item_name']}, 金额: {data['invoice_amount']}")
        
        # 保存到数据库
        conn = sqlite3.connect('reimbursement.db')
        c = conn.cursor()
        c.execute('''INSERT INTO applications 
                     (app_number, purchaser, purchase_details, item_name, product_link, 
                      usage_type, item_type, quantity, purchase_time, invoice_number, 
                      invoice_amount, invoice_date, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (data['app_number'], data['purchaser'], data['purchase_details'], 
                   data['item_name'], data['product_link'], data['usage_type'], 
                   data['item_type'], data['quantity'], data['purchase_time'], 
                   data['invoice_number'], data['invoice_amount'], data['invoice_date'], '待审批'))
        
        # 处理文件上传
        files = request.files.getlist('attachments')
        uploaded_files = []
        for i, file in enumerate(files):
            if file and file.filename:
                # 生成新文件名：发票号码_序号.扩展名
                ext = os.path.splitext(file.filename)[1]
                new_filename = f"{data['invoice_number']}_{i+1}{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                file.save(filepath)
                uploaded_files.append(new_filename)
                
                # 保存附件信息到数据库
                c.execute('''INSERT INTO attachments 
                             (app_number, original_filename, stored_filename, file_path)
                             VALUES (?, ?, ?, ?)''',
                          (app_number, file.filename, new_filename, filepath))
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"申请提交成功 - 申请编号: {app_number}, 上传文件: {uploaded_files}")
        
        return redirect(url_for('success', app_number=app_number))
        
    except Exception as e:
        app.logger.error(f"申请提交失败 - 错误: {str(e)}", exc_info=True)
        flash(f'提交失败：{str(e)}')
        return redirect(url_for('index'))

# 提交成功页面
@app.route('/success/<app_number>')
@log_operation('查看申请结果')
def success(app_number):
    conn = sqlite3.connect('reimbursement.db')
    c = conn.cursor()
    c.execute('SELECT * FROM applications WHERE app_number = ?', (app_number,))
    application = c.fetchone()
    conn.close()
    
    if not application:
        app.logger.warning(f"查找申请失败 - 申请编号不存在: {app_number}")
        flash('申请不存在')
        return redirect(url_for('index'))
    
    app.logger.info(f"用户查看申请结果 - 申请编号: {app_number}, 状态: {application[13]}")
    return render_template('success.html', app_number=app_number, status=application[13])

# 管理员登录页面
@app.route('/admin/login')
@log_operation('访问管理员登录页面')
def admin_login():
    app.logger.info("访问管理员登录页面")
    return render_template('admin_login.html')

# 处理管理员登录
@app.route('/admin/auth', methods=['POST'])
@log_operation('管理员登录验证')
def admin_auth():
    username = request.form['username']
    password = request.form['password']
    
    app.logger.info(f"管理员登录尝试 - 用户名: {username}")
    
    conn = sqlite3.connect('reimbursement.db')
    c = conn.cursor()
    c.execute('SELECT password_hash FROM admins WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    
    if result and check_password_hash(result[0], password):
        session['admin_logged_in'] = True
        session['admin_username'] = username
        app.logger.info(f"管理员登录成功 - 用户名: {username}")
        return redirect(url_for('admin_dashboard'))
    else:
        app.logger.warning(f"管理员登录失败 - 用户名: {username}, 原因: 用户名或密码错误")
        flash('用户名或密码错误')
        return redirect(url_for('admin_login'))

# 管理员后台
@app.route('/admin/dashboard')
@log_operation('访问管理后台')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        app.logger.warning("未登录用户尝试访问管理后台")
        return redirect(url_for('admin_login'))
    
    admin_user = session.get('admin_username')
    
    conn = sqlite3.connect('reimbursement.db')
    c = conn.cursor()
    
    # 获取搜索条件
    search_purchaser = request.args.get('purchaser', '')
    search_status = request.args.get('status', '')
    search_usage = request.args.get('usage', '')
    
    # 获取排序参数
    sort_field = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    # 允许排序的字段
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
    
    search_params = {
        'purchaser': search_purchaser,
        'status': search_status,
        'usage': search_usage,
        'sort': sort_field,
        'order': sort_order
    }
    
    # 构建查询
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
    conn.close()
    
    app.logger.info(f"管理员查看后台 - 用户: {admin_user}, 搜索条件: {search_params}, 结果数量: {len(applications)}")
    
    return render_template('admin_dashboard.html', applications=applications)

# 申请详情和审批
@app.route('/admin/application/<app_number>')
@log_operation('查看申请详情')
def admin_application_detail(app_number):
    if not session.get('admin_logged_in'):
        app.logger.warning(f"未登录用户尝试查看申请详情 - 申请编号: {app_number}")
        return redirect(url_for('admin_login'))
    
    admin_user = session.get('admin_username')
    
    conn = sqlite3.connect('reimbursement.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM applications WHERE app_number = ?', (app_number,))
    application = c.fetchone()
    
    c.execute('SELECT * FROM attachments WHERE app_number = ?', (app_number,))
    attachments = c.fetchall()
    
    conn.close()
    
    if not application:
        app.logger.warning(f"管理员查看不存在的申请 - 用户: {admin_user}, 申请编号: {app_number}")
        flash('申请不存在')
        return redirect(url_for('admin_dashboard'))
    
    app.logger.info(f"管理员查看申请详情 - 用户: {admin_user}, 申请编号: {app_number}, 购买人: {application[2]}, 状态: {application[13]}")
    
    return render_template('admin_detail.html', application=application, attachments=attachments)

# 处理审批
@app.route('/admin/approve/<app_number>', methods=['POST'])
@log_operation('审批申请')
def approve_application(app_number):
    if not session.get('admin_logged_in'):
        app.logger.warning(f"未登录用户尝试审批申请 - 申请编号: {app_number}")
        return redirect(url_for('admin_login'))
    
    admin_user = session.get('admin_username')
    status = request.form['status']
    comment = request.form.get('comment', '')
    
    # 先获取原状态
    conn = sqlite3.connect('reimbursement.db')
    c = conn.cursor()
    c.execute('SELECT status, purchaser FROM applications WHERE app_number = ?', (app_number,))
    old_data = c.fetchone()
    old_status = old_data[0] if old_data else None
    purchaser = old_data[1] if old_data else None
    
    c.execute('UPDATE applications SET status = ?, approval_comment = ?, updated_at = CURRENT_TIMESTAMP WHERE app_number = ?',
              (status, comment, app_number))
    conn.commit()
    conn.close()
    
    app.logger.info(f"管理员审批申请 - 用户: {admin_user}, 申请编号: {app_number}, 购买人: {purchaser}, 状态变更: {old_status} -> {status}, 审批意见: {comment}")
    
    flash('审批完成')
    return redirect(url_for('admin_application_detail', app_number=app_number))

# 导出Excel
@app.route('/admin/export')
@log_operation('导出Excel数据')
def export_excel():
    if not session.get('admin_logged_in'):
        app.logger.warning("未登录用户尝试导出Excel数据")
        return redirect(url_for('admin_login'))
    
    admin_user = session.get('admin_username')
    
    try:
        conn = sqlite3.connect('reimbursement.db')
        df = pd.read_sql_query('SELECT * FROM applications ORDER BY created_at DESC', conn)
        conn.close()
        
        # 重命名列名为中文
        df.columns = ['ID', '申请编号', '购买人', '采购明细', '物品名称', '商品链接', '使用途径', 
                      '物品类型', '数量', '购买时间', '发票号码', '发票金额', '开票日期', 
                      '状态', '审批意见', '创建时间', '更新时间']
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='报销申请', index=False)
        
        output.seek(0)
        filename = f'报销申请_{datetime.now().strftime("%Y%m%d")}.xlsx'
        
        app.logger.info(f"管理员导出Excel - 用户: {admin_user}, 文件名: {filename}, 数据行数: {len(df)}")
        
        return send_file(output, 
                         download_name=filename, 
                         as_attachment=True,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    except Exception as e:
        app.logger.error(f"导出Excel失败 - 用户: {admin_user}, 错误: {str(e)}", exc_info=True)
        flash(f'导出失败：{str(e)}')
        return redirect(url_for('admin_dashboard'))

# 下载附件
@app.route('/download/<filename>')
@log_operation('下载附件')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            app.logger.warning(f"下载文件不存在 - 文件名: {filename}")
            flash('文件不存在')
            return redirect(url_for('admin_dashboard'))
        
        # 查找文件对应的申请信息
        conn = sqlite3.connect('reimbursement.db')
        c = conn.cursor()
        c.execute('SELECT app_number, original_filename FROM attachments WHERE stored_filename = ?', (filename,))
        attachment_info = c.fetchone()
        conn.close()
        
        app_number = attachment_info[0] if attachment_info else 'unknown'
        original_name = attachment_info[1] if attachment_info else filename
        
        user = session.get('admin_username', 'anonymous')
        app.logger.info(f"下载附件 - 用户: {user}, 申请编号: {app_number}, 文件名: {filename}, 原文件名: {original_name}")
        
        return send_file(file_path)
        
    except Exception as e:
        app.logger.error(f"下载附件失败 - 文件名: {filename}, 错误: {str(e)}", exc_info=True)
        flash(f'下载失败：{str(e)}')
        return redirect(url_for('admin_dashboard'))


# 管理员退出
@app.route('/admin/logout')
@log_operation('管理员退出')
def admin_logout():
    admin_user = session.get('admin_username', 'unknown')
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    app.logger.info(f"管理员退出登录 - 用户: {admin_user}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.logger.info("========== 系统启动 ==========")
    app.logger.info("数据库初始化完成")
    app.logger.info("服务器启动在 http://0.0.0.0:5000")
    app.logger.info("日志文件保存在 logs/ 目录下")
    app.run(debug=True, host='0.0.0.0', port=5000) 
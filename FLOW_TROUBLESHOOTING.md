# Flow脚本问题排查指南

## 🚨 问题描述
Flow脚本提交任务后没有反应，页面无变化。

## 🔍 问题诊断
通过运行 `debug_flow_error.py` 脚本，我们发现主要问题是：
- ✅ Flow任务管理器worker正常运行
- ✅ 后端API正常工作  
- ❌ **Chrome没有以调试模式启动，无法连接到浏览器**

## 🚀 解决方案

### 方法1：使用启动脚本（推荐）

#### PowerShell版本
1. 右键点击 `start_chrome_debug.ps1`
2. 选择 "使用PowerShell运行"
3. 等待Chrome启动完成

#### 批处理版本
1. 双击 `start_chrome_debug.bat`
2. 等待Chrome启动完成

### 方法2：手动启动Chrome

1. **关闭所有Chrome进程**
2. **以管理员身份打开命令提示符**
3. **运行以下命令**：

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\你的用户名\chrome-debug-profile"
```

### 方法3：使用现有Chrome（如果已开启调试）

如果Chrome已经以调试模式运行，检查端口：
```cmd
netstat -an | findstr :9222
```

## 📋 启动后的操作步骤

1. **Chrome启动后，访问Flow页面**：
   - 推荐：https://labs.google.com/flow
   - 或者你已有的Flow页面URL

2. **登录Google账户**：
   - 确保已登录
   - 确保有Flow访问权限

3. **等待页面完全加载**：
   - 确保Flow界面完全显示
   - 确保没有加载错误

4. **回到MangoAgent尝试生成视频**：
   - 选择Prompt
   - 选择"Flow (浏览器自动化)"
   - 设置调试端口（默认9222）
   - 点击"开始生成"

## 🔧 端口配置

- **默认端口**：9222
- **如果端口被占用**：脚本会自动尝试9223
- **自定义端口**：可以在启动脚本中修改

## 🐛 常见问题

### 问题1：Chrome启动失败
- 检查Chrome是否正确安装
- 尝试以管理员身份运行
- 检查杀毒软件是否阻止

### 问题2：端口被占用
- 关闭其他Chrome实例
- 使用不同的端口号
- 检查其他应用是否占用端口

### 问题3：Flow页面无法访问
- 检查网络连接
- 确认Google账户权限
- 尝试清除浏览器缓存

### 问题4：自动化仍然失败
- 确保Chrome版本与ChromeDriver兼容
- 检查Flow页面结构是否变化
- 查看后端日志获取详细错误信息

## 📊 状态检查

运行以下命令检查状态：
```bash
python debug_flow_error.py
```

正常状态应该是：
- ✅ Flow任务管理器已导入
- ✅ Worker启动成功
- ✅ 找到可用端口: 9222
- ✅ 端口响应正常

## 💡 预防措施

1. **定期更新Chrome**：保持最新版本
2. **使用专用用户数据目录**：避免与日常Chrome冲突
3. **监控端口占用**：定期检查调试端口状态
4. **备份配置**：保存成功的Chrome启动参数

## 🆘 获取帮助

如果问题仍然存在：
1. 运行 `debug_flow_error.py` 获取详细错误信息
2. 检查后端日志文件
3. 确认Chrome和ChromeDriver版本兼容性
4. 尝试在不同的Chrome用户数据目录中运行

---

**记住**：Flow脚本需要Chrome以调试模式运行才能工作。这是正常的安全机制，不是bug。

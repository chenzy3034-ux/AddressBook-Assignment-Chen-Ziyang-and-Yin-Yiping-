from urllib.parse import urlencode

from flask import has_request_context, request, session, url_for


ZH = {
    "Address Book": "通讯录",
    "My address book": "我的通讯录",
    "Contacts": "联系人",
    "Add contact": "新建联系人",
    "Language": "界面语言",
    "All contacts": "全部联系人",
    "Favorite contacts": "特别关注",
    "Contact methods": "联系方式",
    "{count} contact in total": "共 {count} 位联系人",
    "{count} contacts in total": "共 {count} 位联系人",
    "Contact search and filters": "联系人搜索与筛选",
    "Search contacts": "搜索联系人",
    "Search by name or contact details": "搜索姓名或联系方式",
    "Search": "搜索",
    "Clear": "清除",
    "Contact filters": "联系人筛选",
    "Excel import and export": "Excel 导入与导出",
    "Choose .xlsx file": "选择 .xlsx 文件",
    "Select file": "选择文件",
    "No file selected": "未选择文件",
    "Import": "导入",
    "Download example": "下载模板",
    "Export contacts": "导出联系人",
    "Remove {name} from favorites": "取消关注{name}",
    "Add {name} to favorites": "特别关注{name}",
    "Remove from favorites": "取消关注",
    "Add to favorites": "特别关注",
    "View": "查看",
    "No matching contacts": "没有匹配的联系人",
    "Try a different name, phone number, email, label, or address.": "试试其他姓名、电话、邮箱、标签或地址。",
    "Clear search": "清除搜索",
    "No favorite contacts": "还没有特别关注的联系人",
    "Select the star beside a contact to add it to your favorites.": "点击联系人旁的星标即可特别关注。",
    "View all contacts": "查看全部联系人",
    "No contacts yet": "还没有联系人",
    "Add first contact": "添加第一位联系人",
    "Back to contacts": "返回联系人列表",
    "A name and at least one contact method are required.": "请填写姓名和至少一种联系方式。",
    "Name": "姓名",
    "Add method": "添加方式",
    "Type": "类型",
    "Label": "标签",
    "Value": "内容",
    "Mobile, work, personal": "手机、工作、个人",
    "Phone, email, username, or address": "电话、邮箱、账号或地址",
    "Remove contact method": "移除此联系方式",
    "Remove": "移除",
    "Save contact": "保存联系人",
    "Cancel": "取消",
    "Favorite contact": "特别关注",
    "Edit contact": "编辑联系人",
    "Delete contact": "删除联系人",
    "Delete this contact?": "确定删除这位联系人吗？",
    "Page not found": "找不到页面",
    "Return to contacts": "返回通讯录",
    "Phone numbers": "电话号码",
    "Email addresses": "电子邮箱",
    "Social media": "社交账号",
    "Postal addresses": "邮寄地址",
    "Phone": "电话",
    "Email": "邮箱",
    "Social": "社交账号",
    "Address": "地址",
    "Name is required.": "请填写姓名。",
    "At least one contact method is required.": "请填写至少一种联系方式。",
    "Select a valid contact method type.": "请选择有效的联系方式类型。",
    "Contact created successfully.": "联系人已创建。",
    "Contact updated successfully.": "联系人已更新。",
    "{name} was added to favorites.": "已特别关注{name}。",
    "{name} was removed from favorites.": "已取消关注{name}。",
    "{name} was deleted.": "已删除{name}。",
    "Choose an Excel file to import.": "请选择要导入的 Excel 文件。",
    "Only .xlsx files are supported.": "仅支持 .xlsx 文件。",
    "The Excel file must be 5 MB or smaller.": "Excel 文件不能超过 5 MB。",
    "The Excel file could not be imported.": "无法导入 Excel 文件。请检查文件格式。",
    "The Excel file could not be imported: {reason}": "无法导入 Excel 文件：{reason}",
    "Imported {imported} contact(s). Skipped {duplicates} duplicate(s). Ignored {invalid} invalid row(s).": "已导入 {imported} 位联系人，跳过 {duplicates} 条重复记录，忽略 {invalid} 条无效记录。",
    "Favorite must be Yes or No.": "Favorite 列必须填 Yes 或 No。",
    "The workbook is too large after decompression.": "工作簿解压后过大。",
    "The workbook is empty.": "工作簿为空。",
    "The workbook contains duplicate column headers.": "工作簿包含重复的列名。",
    "The workbook must contain Name and Favorite columns.": "工作簿必须包含 Name 和 Favorite 两列。",
    "Unsupported column header: {header}.": "不支持列名“{header}”。",
    "The workbook must contain at least one contact method column.": "工作簿中至少要有一列联系方式。",
    "The workbook cannot contain more than {count} rows.": "工作簿不能超过 {count} 行。",
    "Row {row}: {reason}": "第 {row} 行：{reason}",
}


def language():
    if has_request_context() and session.get("language") == "zh-CN":
        return "zh-CN"
    return "en"


def translate(message, **values):
    translated = ZH.get(message, message) if language() == "zh-CN" else message
    return translated.format(**values) if values else translated


def init_app(app):
    @app.before_request
    def remember_language():
        chosen = request.args.get("lang")
        if request.method == "GET" and chosen in ("en", "zh-CN") and session.get("language") != chosen:
            session["language"] = chosen

    @app.template_global()
    def language_url(chosen):
        endpoint = request.endpoint or "contacts.index"
        path = url_for(endpoint, **(request.view_args or {}))
        parameters = [
            (name, value)
            for name, value in request.args.items(multi=True)
            if name != "lang"
        ]
        parameters.append(("lang", chosen))
        return f"{path}?{urlencode(parameters)}"

    app.add_template_global(language)
    app.add_template_global(translate, "t")

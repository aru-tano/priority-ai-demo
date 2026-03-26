// ═══════════════════════════════════════════════════════════════
// 教頭ダッシュボード GAS Web App
// スプレッドシートID: 1bc8UShEyzy38uQhnI1dXCKfns3u_M4GqxaxLVxqLC70
// ═══════════════════════════════════════════════════════════════

// ★★★ ここにあなたのスプレッドシートIDを貼ってください（セットアップガイド参照）★★★
const SS_ID = 'ここにスプレッドシートIDを貼る';

// ===== doGet: シート→JSON =====
function doGet(e) {
  const action = (e && e.parameter && e.parameter.action) || 'tasks';

  let result;
  if (action === 'tasks') {
    result = getTasks();
  } else if (action === 'diary') {
    result = getDiary();
  } else if (action === 'staff') {
    result = getStaff();
  } else {
    result = { error: 'Unknown action: ' + action };
  }

  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

// ===== doPost: 変更受付 =====
function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  const action = body.action;

  let result;
  if (action === 'update_status') {
    result = updateStatus(body.id, body.status);
  } else if (action === 'update_date') {
    result = updateDate(body.id, body.date);
  } else if (action === 'add_task') {
    result = addTask(body.task);
  } else if (action === 'add_diary') {
    result = addDiary(body.entry);
  } else if (action === 'update_assignee') {
    result = updateAssignee(body.id, body.assignee, body.dueDate);
  } else if (action === 'add_staff') {
    result = addStaff(body.record);
  } else {
    result = { error: 'Unknown action: ' + action };
  }

  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

// ═══════════════════════════════════════════════════════════════
// READ: シート1（タスク）→ JSON配列
// ═══════════════════════════════════════════════════════════════
function getTasks() {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('タスク一覧 ');
  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  // 列インデックスをヘッダー名で取得
  const col = {};
  headers.forEach((h, i) => col[h] = i);

  const tasks = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[col['タスク']]) continue; // タスク名が空なら飛ばす

    tasks.push({
      id: row[col['案件ID']] || 'KD-R8-' + String(i).padStart(3, '0'),
      date: formatDate(row[col['日付']]),
      task: row[col['タスク']],
      status: row[col['状態']] || '未着手',
      priority: row[col['重要度']] || '',
      category: row[col['カテゴリ']] || '',
      timeSlot: row[col['時間帯']] || '',
      calendar: row[col['カレンダー']] || '',
      timer: row[col['準備タイマー']] || '',
      detail: row[col['詳細']] || '',
      source: row[col['出典']] || '',
      dow: row[col['曜日']] || '',
      urgency: row[col['緊急度']] || '',
      adhoc: row[col['突発']] || '',
      assignee: row[col['担当者']] || '',
      dueDate: formatDate(row[col['回収予定日']]),
      _row: i + 1 // シート上の実行番号（書き戻し用）
    });
  }

  return { tasks: tasks, count: tasks.length, updated: new Date().toISOString() };
}

// ═══════════════════════════════════════════════════════════════
// READ: 日誌・メモ → JSON配列
// ═══════════════════════════════════════════════════════════════
function getDiary() {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('日誌・メモ');
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const col = {};
  headers.forEach((h, i) => col[h] = i);

  const entries = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[col['内容']]) continue;
    entries.push({
      date: formatDate(row[col['日付']]),
      time: row[col['時刻']] || '',
      type: row[col['種別']] || '',
      content: row[col['内容']],
      isTodo: row[col['→TODO?']] || '',
      memo: row[col['対応・メモ']] || '',
      follow: row[col['フォロー']] || '',
      _row: i + 1
    });
  }

  return { entries: entries, count: entries.length };
}

// ═══════════════════════════════════════════════════════════════
// READ: 職員動態 → JSON配列
// ═══════════════════════════════════════════════════════════════
function getStaff() {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('職員動態');
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const col = {};
  headers.forEach((h, i) => col[h] = i);

  const records = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (!row[col['名前']]) continue;
    records.push({
      date: formatDate(row[col['日付']]),
      name: row[col['名前']],
      type: row[col['種別']] || '',
      timeSlot: row[col['時間帯']] || '',
      note: row[col['備考']] || '',
      _row: i + 1
    });
  }

  return { records: records, count: records.length };
}

// ═══════════════════════════════════════════════════════════════
// WRITE: ステータス変更
// ═══════════════════════════════════════════════════════════════
function updateStatus(id, newStatus) {
  const row = findRowById(id);
  if (!row) return { error: 'ID not found: ' + id };

  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('タスク一覧 ');
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const statusCol = headers.indexOf('状態') + 1;

  sheet.getRange(row, statusCol).setValue(newStatus);
  return { ok: true, id: id, status: newStatus };
}

// ═══════════════════════════════════════════════════════════════
// WRITE: 日付変更（カレンダードラッグ用）
// ═══════════════════════════════════════════════════════════════
function updateDate(id, newDate) {
  const row = findRowById(id);
  if (!row) return { error: 'ID not found: ' + id };

  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('タスク一覧 ');
  // A列が日付
  sheet.getRange(row, 1).setValue(newDate);
  return { ok: true, id: id, date: newDate };
}

// ═══════════════════════════════════════════════════════════════
// WRITE: タスク追加
// ═══════════════════════════════════════════════════════════════
function addTask(task) {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('タスク一覧 ');
  const lastRow = sheet.getLastRow();
  const nextNum = lastRow; // ヘッダー除いた行数
  const newId = 'KD-R8-' + String(nextNum).padStart(3, '0');

  sheet.appendRow([
    task.date || '',
    task.task || '',
    task.status || '未着手',
    task.priority || '中',
    task.category || '',
    task.timeSlot || '',
    '', // カレンダー
    '', // 準備タイマー
    task.detail || '',
    'web', // 出典
    '', // 曜日
    '', // 緊急度
    '', // 突発
    newId,
    task.assignee || '',
    task.dueDate || ''
  ]);

  return { ok: true, id: newId, row: lastRow + 1 };
}

// ═══════════════════════════════════════════════════════════════
// WRITE: 日誌・メモ追加（VoicePad日記用）
// ═══════════════════════════════════════════════════════════════
function addDiary(entry) {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('日誌・メモ');

  sheet.appendRow([
    entry.date || new Date(),
    entry.time || '',
    entry.type || '音声メモ',
    entry.content || '',
    '', // →TODO?
    entry.memo || '',
    '' // フォロー
  ]);

  return { ok: true };
}

// ═══════════════════════════════════════════════════════════════
// WRITE: 職員動態追加
// ═══════════════════════════════════════════════════════════════
function addStaff(record) {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('職員動態');

  sheet.appendRow([
    record.date || new Date(),
    record.name || '',
    record.type || '',
    record.timeSlot || '',
    record.note || ''
  ]);

  return { ok: true };
}

// ═══════════════════════════════════════════════════════════════
// WRITE: 担当者（委任先）+ 回収予定日 書き戻し
// ═══════════════════════════════════════════════════════════════
function updateAssignee(id, assignee, dueDate) {
  const row = findRowById(id);
  if (!row) return { error: 'ID not found: ' + id };

  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('タスク一覧 ');
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];

  const assigneeCol = headers.indexOf('担当者') + 1;
  const dueCol = headers.indexOf('回収予定日') + 1;

  if (assigneeCol > 0) sheet.getRange(row, assigneeCol).setValue(assignee || '');
  if (dueCol > 0 && dueDate) sheet.getRange(row, dueCol).setValue(dueDate);

  return { ok: true, id: id, assignee: assignee, dueDate: dueDate || '' };
}

// ═══════════════════════════════════════════════════════════════
// UTIL
// ═══════════════════════════════════════════════════════════════
function findRowById(id) {
  const ss = SpreadsheetApp.openById(SS_ID);
  const sheet = ss.getSheetByName('タスク一覧 ');
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const idCol = headers.indexOf('案件ID') + 1;
  if (idCol === 0) return null;

  const ids = sheet.getRange(2, idCol, sheet.getLastRow() - 1, 1).getValues();
  for (let i = 0; i < ids.length; i++) {
    if (ids[i][0] === id) return i + 2;
  }
  return null;
}

function formatDate(val) {
  if (!val) return '';
  if (val instanceof Date) {
    const y = val.getFullYear();
    const m = String(val.getMonth() + 1).padStart(2, '0');
    const d = String(val.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + d;
  }
  return String(val);
}

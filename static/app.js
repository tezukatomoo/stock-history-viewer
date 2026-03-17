// ===== State =====
let allEvents = [];
let categories = [];
let stockIndices = [];
let selectedEvent = null;
let selectedSimilarIds = [];
let stockChart = null;
let compareChart = null;

// 重要日付データ（チャート上にマーカー表示）
const keyDatesData = {
    1: [
        {date: "1950-06-25", label: "北朝鮮が韓国に侵攻"},
        {date: "1950-06-27", label: "米国が参戦決定"},
        {date: "1950-09-15", label: "仁川上陸作戦"},
        {date: "1950-10-19", label: "中国人民志願軍が参戦"},
        {date: "1950-11-30", label: "中国軍の大規模反撃"}
    ],
    2: [
        {date: "1956-07-26", label: "ナセルがスエズ運河国有化宣言"},
        {date: "1956-10-29", label: "イスラエルがシナイ半島侵攻"},
        {date: "1956-11-05", label: "英仏が上陸作戦開始"},
        {date: "1956-11-06", label: "米ソの圧力で停戦"}
    ],
    3: [
        {date: "1962-10-16", label: "ケネディにミサイル配備の情報"},
        {date: "1962-10-22", label: "ケネディが海上封鎖を発表"},
        {date: "1962-10-24", label: "ソ連船が封鎖線に接近"},
        {date: "1962-10-26", label: "フルシチョフが撤去提案"},
        {date: "1962-10-28", label: "ソ連がミサイル撤去に合意"}
    ],
    4: [
        {date: "1964-08-02", label: "トンキン湾事件"},
        {date: "1964-08-07", label: "トンキン湾決議（戦争権限）"},
        {date: "1965-03-08", label: "米海兵隊がダナンに上陸"},
        {date: "1968-01-30", label: "テト攻勢"},
        {date: "1973-01-27", label: "パリ和平協定"},
        {date: "1975-04-30", label: "サイゴン陥落"}
    ],
    5: [
        {date: "1973-10-06", label: "エジプト・シリアがイスラエル攻撃"},
        {date: "1973-10-17", label: "OAPEC石油禁輸を発表"},
        {date: "1973-10-25", label: "国連安保理が停戦決議"},
        {date: "1974-01-18", label: "イスラエル・エジプト撤退合意"}
    ],
    6: [
        {date: "1978-09-08", label: "黒い金曜日（テヘラン戒厳令）"},
        {date: "1979-01-16", label: "パーレビ国王が国外脱出"},
        {date: "1979-02-01", label: "ホメイニ帰国"},
        {date: "1979-02-11", label: "イラン・イスラム共和国成立"},
        {date: "1979-11-04", label: "在テヘラン米大使館占拠事件"}
    ],
    7: [
        {date: "1982-04-02", label: "アルゼンチンがフォークランド占拠"},
        {date: "1982-04-25", label: "英軍がサウスジョージア奪還"},
        {date: "1982-05-02", label: "英軍が巡洋艦ベルグラノ撃沈"},
        {date: "1982-05-21", label: "英軍がフォークランド上陸"},
        {date: "1982-06-14", label: "アルゼンチン降伏"}
    ],
    8: [
        {date: "1987-10-14", label: "米貿易赤字悪化で株安開始"},
        {date: "1987-10-16", label: "金曜日に大幅下落"},
        {date: "1987-10-19", label: "ブラックマンデー（-22.6%）"},
        {date: "1987-10-20", label: "FRBが流動性供給を声明"}
    ],
    9: [
        {date: "1990-08-02", label: "イラクがクウェート侵攻"},
        {date: "1990-08-06", label: "国連が経済制裁決議"},
        {date: "1990-11-29", label: "国連が武力行使容認決議"},
        {date: "1991-01-17", label: "多国籍軍の空爆開始（砂漠の嵐）"},
        {date: "1991-02-24", label: "地上戦開始"},
        {date: "1991-02-28", label: "停戦"}
    ],
    10: [
        {date: "1989-12-29", label: "日経平均が史上最高値38,957円"},
        {date: "1990-01-04", label: "大発会から暴落開始"},
        {date: "1990-04-02", label: "一時28,000円台に下落"},
        {date: "1990-10-01", label: "20,000円割れ"},
        {date: "1992-08-18", label: "14,309円まで下落"}
    ],
    11: [
        {date: "1997-07-02", label: "タイバーツが変動相場制に移行"},
        {date: "1997-08-14", label: "インドネシアルピア暴落"},
        {date: "1997-10-23", label: "香港株が暴落"},
        {date: "1997-11-17", label: "韓国ウォン急落"},
        {date: "1997-11-21", label: "韓国がIMFに支援要請"},
        {date: "1997-12-03", label: "IMFが韓国に580億ドル支援"}
    ],
    12: [
        {date: "1998-08-17", label: "ロシアがデフォルト宣言"},
        {date: "1998-08-21", label: "ルーブル暴落"},
        {date: "1998-09-02", label: "LTCM巨額損失が判明"},
        {date: "1998-09-23", label: "FRBがLTCM救済を調整"},
        {date: "1998-09-29", label: "FRBが緊急利下げ"}
    ],
    13: [
        {date: "1999-03-24", label: "NATO空爆開始"},
        {date: "1999-04-23", label: "NATO50周年で方針確認"},
        {date: "1999-06-03", label: "ミロシェビッチが和平案受入"},
        {date: "1999-06-10", label: "空爆停止"}
    ],
    14: [
        {date: "2000-03-10", label: "NASDAQ最高値5,048"},
        {date: "2000-04-03", label: "マイクロソフト独禁法判決"},
        {date: "2000-04-14", label: "NASDAQが1週間で25%暴落"},
        {date: "2001-01-03", label: "FRBが緊急利下げ"},
        {date: "2001-03-12", label: "NASDAQ2,000割れ"},
        {date: "2002-07-23", label: "ワールドコム破綻"},
        {date: "2002-10-09", label: "NASDAQ底値1,114"}
    ],
    15: [
        {date: "2001-09-11", label: "ハイジャック機がWTCに衝突"},
        {date: "2001-09-14", label: "ブッシュが非常事態宣言"},
        {date: "2001-09-17", label: "NY証券取引所が6日ぶり再開"},
        {date: "2001-09-21", label: "ダウが8,235（底値）"},
        {date: "2001-10-07", label: "米軍がアフガニスタン攻撃開始"}
    ],
    16: [
        {date: "2003-02-05", label: "パウエル国連演説（大量破壊兵器）"},
        {date: "2003-03-17", label: "ブッシュが最後通牒"},
        {date: "2003-03-20", label: "米英軍の空爆開始"},
        {date: "2003-04-09", label: "バグダッド陥落"},
        {date: "2003-05-01", label: "ブッシュ「大規模戦闘終結」宣言"},
        {date: "2003-12-13", label: "フセイン拘束"}
    ],
    17: [
        {date: "2003-02-10", label: "WHO広東省の異常肺炎を報告"},
        {date: "2003-03-12", label: "WHOがグローバル警報"},
        {date: "2003-03-15", label: "WHOが渡航勧告"},
        {date: "2003-04-16", label: "病原体がコロナウイルスと特定"},
        {date: "2003-07-05", label: "WHO封じ込め成功を宣言"}
    ],
    18: [
        {date: "2007-08-09", label: "BNPパリバショック"},
        {date: "2008-03-16", label: "ベアスターンズ救済合併"},
        {date: "2008-09-07", label: "ファニーメイ・フレディマック国有化"},
        {date: "2008-09-15", label: "リーマン・ブラザーズ破綻"},
        {date: "2008-09-16", label: "AIG救済（850億ドル）"},
        {date: "2008-10-03", label: "TARP（7000億ドル）成立"},
        {date: "2008-10-10", label: "ダウが1週間で22%下落"},
        {date: "2008-11-25", label: "FRBがQE1開始"},
        {date: "2009-03-09", label: "S&P500底値666"}
    ],
    19: [
        {date: "2009-12-08", label: "フィッチがギリシャ格下げ"},
        {date: "2010-04-23", label: "ギリシャがEU/IMFに支援要請"},
        {date: "2010-05-02", label: "ギリシャ第1次支援1100億ユーロ"},
        {date: "2010-05-06", label: "フラッシュクラッシュ"},
        {date: "2011-07-21", label: "ギリシャ第2次支援合意"},
        {date: "2011-11-01", label: "パパンドレウが国民投票提案→撤回"},
        {date: "2012-07-26", label: "ドラギ「何でもやる」発言"}
    ],
    20: [
        {date: "2011-03-11", label: "M9.0地震発生（14:46）"},
        {date: "2011-03-12", label: "福島第一原発1号機水素爆発"},
        {date: "2011-03-14", label: "3号機水素爆発・計画停電開始"},
        {date: "2011-03-15", label: "日経平均が1日で10.6%暴落"},
        {date: "2011-03-17", label: "G7協調介入（円売り）"},
        {date: "2011-03-18", label: "日銀が追加緩和"}
    ],
    21: [
        {date: "2014-02-22", label: "ヤヌコビッチ大統領逃亡"},
        {date: "2014-02-27", label: "武装勢力がクリミア議会占拠"},
        {date: "2014-03-01", label: "ロシア議会がウクライナ派兵承認"},
        {date: "2014-03-16", label: "クリミア住民投票"},
        {date: "2014-03-18", label: "ロシアがクリミア編入条約"}
    ],
    22: [
        {date: "2015-06-12", label: "上海総合が最高値5,178"},
        {date: "2015-07-08", label: "中国政府が株式売却禁止令"},
        {date: "2015-08-11", label: "中国が人民元を切り下げ"},
        {date: "2015-08-24", label: "世界同時株安（ブラックマンデー）"},
        {date: "2016-01-04", label: "中国サーキットブレーカー発動"},
        {date: "2016-02-12", label: "世界株安の底"}
    ],
    23: [
        {date: "2016-06-23", label: "英国EU離脱の国民投票"},
        {date: "2016-06-24", label: "離脱派勝利が判明・市場暴落"},
        {date: "2016-06-24", label: "キャメロン首相が辞意表明"},
        {date: "2016-06-27", label: "英ポンドが31年ぶり安値"}
    ],
    24: [
        {date: "2018-03-22", label: "トランプが対中関税に署名"},
        {date: "2018-04-03", label: "中国が報復関税発表"},
        {date: "2018-07-06", label: "米が340億ドル関税発動"},
        {date: "2018-09-24", label: "2000億ドル追加関税"},
        {date: "2018-12-01", label: "G20で90日間猶予合意"},
        {date: "2018-12-24", label: "ダウ年初来安値"},
        {date: "2019-05-10", label: "対中関税25%に引上げ"},
        {date: "2019-08-05", label: "中国が人民元7元台に切下げ"},
        {date: "2020-01-15", label: "第1段階合意に署名"}
    ],
    25: [
        {date: "2020-01-23", label: "武漢封鎖"},
        {date: "2020-02-24", label: "イタリアで感染急拡大"},
        {date: "2020-03-03", label: "FRBが緊急利下げ0.5%"},
        {date: "2020-03-09", label: "ダウが2,013ドル暴落"},
        {date: "2020-03-11", label: "WHOがパンデミック宣言"},
        {date: "2020-03-13", label: "トランプが国家非常事態宣言"},
        {date: "2020-03-15", label: "FRBがゼロ金利+QE発表"},
        {date: "2020-03-16", label: "ダウが2,997ドル暴落（史上最大）"},
        {date: "2020-03-23", label: "S&P500底値2,237"},
        {date: "2020-03-27", label: "CARES Act（2.2兆ドル）成立"}
    ],
    26: [
        {date: "2022-02-24", label: "ロシアがウクライナ全面侵攻"},
        {date: "2022-02-26", label: "SWIFTからロシア排除決定"},
        {date: "2022-02-28", label: "ロシア中銀が金利20%に"},
        {date: "2022-03-08", label: "原油130ドル超（14年ぶり高値）"},
        {date: "2022-03-16", label: "FRBが利上げ開始"},
        {date: "2022-04-08", label: "EU ロシア石炭禁輸"},
        {date: "2022-05-09", label: "プーチン戦勝記念日演説"},
        {date: "2022-09-21", label: "プーチン部分動員令"},
        {date: "2022-09-30", label: "ロシアが4州併合宣言"}
    ],
    27: [
        {date: "2023-03-08", label: "シルバーゲート銀行が清算発表"},
        {date: "2023-03-10", label: "SVBが経営破綻"},
        {date: "2023-03-12", label: "シグネチャー銀行も破綻"},
        {date: "2023-03-12", label: "FDIC・FRBが預金全額保護発表"},
        {date: "2023-03-15", label: "クレディスイス株が暴落"},
        {date: "2023-03-19", label: "UBSがクレディスイス買収"}
    ],
    28: [
        {date: "2023-10-07", label: "ハマスがイスラエルを大規模攻撃"},
        {date: "2023-10-09", label: "イスラエルがガザに報復空爆"},
        {date: "2023-10-13", label: "イスラエルがガザ北部に避難命令"},
        {date: "2023-10-27", label: "イスラエルがガザ地上侵攻開始"},
        {date: "2023-11-15", label: "ガザのシファ病院に突入"},
        {date: "2023-11-24", label: "一時停戦・人質交換"},
        {date: "2024-01-26", label: "ICJがジェノサイド訴訟で暫定命令"}
    ],
    29: [
        {date: "2020-01-03", label: "米軍がソレイマニ司令官を殺害"},
        {date: "2020-01-05", label: "イラクが米軍撤退を決議"},
        {date: "2020-01-07", label: "イランが米軍基地にミサイル"},
        {date: "2020-01-08", label: "トランプ「戦争を望まない」"},
        {date: "2020-01-08", label: "ウクライナ機誤射撃墜"}
    ],
    30: [
        {date: "2025-04-02", label: "トランプが相互関税を発表"},
        {date: "2025-04-03", label: "S&P500が4.8%暴落"},
        {date: "2025-04-04", label: "中国が34%報復関税発表"},
        {date: "2025-04-07", label: "ダウ先物が一時2,500ドル安"},
        {date: "2025-04-09", label: "トランプが90日間停止を発表"},
        {date: "2025-04-09", label: "S&P500が9.5%急騰（歴史的反発）"}
    ]
};

// 日本への影響データ（各イベントID別）
const japanImpactData = {
    1: "朝鮮戦争特需で日本経済は急回復。繊維・金属産業が活況。GDPが戦前水準を回復するきっかけに。",
    5: "原油輸入の99%を中東に依存していた日本に深刻な打撃。狂乱物価・トイレットペーパー買い占め騒動。日経平均は大幅下落し、高度経済成長が終焉。",
    6: "第二次オイルショックで物価上昇。省エネ技術の発展につながり、日本車の燃費性能が世界で評価される契機に。",
    8: "ブラックマンデーで日経平均は翌日14.9%下落（3,836円安）。しかしバブル景気の勢いで他市場より早く回復。",
    9: "湾岸戦争で原油価格が急騰。日経平均はバブル崩壊と重なり大幅下落。石油備蓄の重要性が再認識された。",
    10: "日経平均が38,957円から大暴落。不動産・株式バブルの崩壊で「失われた30年」が始まる。金融機関の不良債権問題が深刻化。",
    11: "アジア通貨危機で日本の金融機関も影響。山一證券・北海道拓殖銀行が破綻。日経平均も大幅下落。",
    14: "ITバブル崩壊で日本のIT関連株も暴落。ソフトバンクなどが大幅下落。日経平均は2003年に7,603円のバブル後最安値。",
    15: "同時多発テロの翌日、日経平均は約6%下落。航空・旅行関連株が急落。円は安全資産として買われ円高に。",
    18: "リーマンショックで日経平均は約60%下落。輸出産業が壊滅的打撃。円高が進行し1ドル=75円台に。派遣切り・就職氷河期が社会問題に。",
    20: "東日本大震災で日経平均は3日間で約17.5%暴落。福島原発事故で全国の原発が停止。電力不足・計画停電。復興需要で建設株は後に上昇。",
    22: "チャイナショックで日経平均は約20%下落。中国経済減速懸念から輸出関連株が売られた。",
    23: "Brexit国民投票の結果を受け、日経平均は1日で約8%（1,286円）暴落。円が急伸し一時99円台に。",
    24: "米中貿易戦争で日本の製造業にも影響。サプライチェーンの中国依存リスクが顕在化。日経平均も連動して下落。",
    25: "コロナショックで日経平均は約31%下落（24,000→16,500円台）。緊急事態宣言・外出自粛で経済活動が停滞。大規模財政出動と金融緩和で回復。",
    26: "ロシア・ウクライナ戦争でエネルギー・食料価格が急騰。円安が加速し1ドル=150円台に。輸入コスト増で物価上昇。資源のない日本の脆弱性が露呈。",
    28: "中東情勢悪化で原油価格に上昇圧力。日本は中東からの原油輸入が9割超。ホルムズ海峡のリスクが再び注目。",
    30: "トランプ関税で日経平均は大幅下落。自動車関税の影響が特に懸念され、トヨタ等の株が売られた。円高も進行。"
};

// ===== Init =====
document.addEventListener('DOMContentLoaded', async () => {
    const data = await fetch('/api/events').then(r => r.json());
    allEvents = data.events;
    categories = data.categories;
    stockIndices = data.stock_indices;

    // カテゴリフィルタ
    const select = document.getElementById('categoryFilter');
    categories.forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat.id;
        opt.textContent = cat.name;
        select.appendChild(opt);
    });

    // 初回描画
    renderTimeline(allEvents, 1950, 2026);
    setupListeners();
});

// ===== Timeline =====
function renderTimeline(events, startYear, endYear) {
    const container = document.getElementById('timeline');
    container.innerHTML = '';

    const track = document.createElement('div');
    track.className = 'timeline-track';
    const totalYears = endYear - startYear;

    // 年ラベル
    const step = totalYears <= 30 ? 5 : 10;
    for (let y = startYear; y <= endYear; y += step) {
        const label = document.createElement('div');
        label.className = 'timeline-year-label';
        label.style.left = ((y - startYear) / totalYears * 100) + '%';
        label.textContent = y;
        track.appendChild(label);
    }

    // イベントドット
    events.forEach(event => {
        const eventYear = new Date(event.start_date).getFullYear();
        const eventDate = new Date(event.start_date);
        const yearFraction = eventYear + (eventDate.getMonth() / 12);

        if (yearFraction < startYear || yearFraction > endYear) return;

        const pct = ((yearFraction - startYear) / totalYears * 100);
        const cat = categories.find(c => c.id === event.category);

        const dot = document.createElement('div');
        dot.className = 'timeline-event';
        dot.style.left = pct + '%';
        dot.style.backgroundColor = cat ? cat.color : '#4a8cff';
        dot.dataset.eventId = event.id;

        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.innerHTML = `<strong>${event.name}</strong><br><span class="tooltip-date">${event.start_date}</span>`;
        dot.appendChild(tooltip);

        dot.addEventListener('click', () => showEventDetail(event));
        track.appendChild(dot);
    });

    container.appendChild(track);
}

// ===== Search & Filter =====
function filterEvents() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const category = document.getElementById('categoryFilter').value;

    let filtered = allEvents;
    if (category) {
        filtered = filtered.filter(e => e.category === category);
    }
    if (query) {
        filtered = filtered.filter(e => {
            const searchable = (
                e.name + e.name_en + e.description + (e.tags || []).join(' ')
            ).toLowerCase();
            return searchable.includes(query);
        });
    }

    const startYear = parseInt(document.querySelector('.era-btn.active').dataset.start);
    const endYear = parseInt(document.querySelector('.era-btn.active').dataset.end);
    renderTimeline(filtered, startYear, endYear);
}

// ===== Event Detail =====
function showEventDetail(event) {
    selectedEvent = event;
    selectedSimilarIds = [];

    const section = document.getElementById('detailSection');
    section.style.display = 'block';
    section.scrollIntoView({ behavior: 'smooth' });

    document.getElementById('eventTitle').textContent = event.name;
    document.getElementById('eventDescription').textContent = event.description;
    document.getElementById('eventMarketImpact').textContent = event.market_impact;

    const cat = categories.find(c => c.id === event.category);
    const badge = document.getElementById('eventCategory');
    badge.textContent = cat ? cat.name : '';
    badge.style.backgroundColor = cat ? cat.color : '#4a8cff';

    document.getElementById('eventDates').textContent =
        `${event.start_date} 〜 ${event.end_date}`;

    // 日本への影響
    const japanBox = document.getElementById('japanImpactBox');
    if (japanImpactData[event.id]) {
        japanBox.style.display = 'block';
        document.getElementById('japanImpactText').textContent = japanImpactData[event.id];
    } else {
        japanBox.style.display = 'none';
    }

    // 重要日付リスト
    renderKeyDates(event);

    // 指標選択チップ
    renderIndexSelector(event);

    // チャートをリセット
    document.getElementById('chartContainer').style.display = 'none';
    document.getElementById('compareChartContainer').style.display = 'none';
    if (stockChart) { stockChart.destroy(); stockChart = null; }
    if (compareChart) { compareChart.destroy(); compareChart = null; }

    // 類似イベント取得
    loadSimilarEvents(event.id);
}

function renderKeyDates(event) {
    const section = document.getElementById('keyDatesSection');
    const list = document.getElementById('keyDatesList');
    const dates = keyDatesData[event.id];

    if (!dates || dates.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    list.innerHTML = '';

    const markerColors = [
        '#ff9f43', '#feca57', '#54a0ff', '#5f27cd', '#01a3a4',
        '#ff6b6b', '#48dbfb', '#ff9ff3', '#00d2d3', '#c8d6e5'
    ];

    dates.forEach((kd, i) => {
        const color = markerColors[i % markerColors.length];
        const item = document.createElement('div');
        item.className = 'key-date-item';
        item.style.setProperty('--dot-color', color);
        item.innerHTML = `
            <span class="kd-date">${kd.date}</span>
            <span class="kd-label">${kd.label}</span>
        `;
        item.style.cssText = `position:relative;padding:6px 0 6px 16px;font-size:0.82rem;`;
        // ドットの色を動的に設定
        item.addEventListener('mouseenter', () => item.style.color = color);
        item.addEventListener('mouseleave', () => item.style.color = '');
        list.appendChild(item);

        // ::before の色を個別設定するため、スタイルを直接追加
        const style = document.createElement('style');
        style.textContent = `.key-date-item:nth-child(${i + 1})::before { border-color: ${color}; }`;
        list.appendChild(style);
    });
}

function renderIndexSelector(event) {
    const container = document.getElementById('indexSelector');
    container.innerHTML = '';

    // グループ分け
    const groups = {
        '主要株式指数': ['^DJI', '^GSPC', '^IXIC', '^N225', '^FTSE', '^GDAXI', '^HSI'],
        'アジア・新興国・資源国': ['^KS11', '^BSESN', '^GSPTSE', 'EEM', 'FXI', 'EWJ'],
        'セクターETF（業種別）': ['XLE', 'XLF', 'XLV', 'XLU', 'ITA', 'HACK', 'URA'],
        'エネルギー': ['CL=F', 'NG=F'],
        '貴金属・工業金属': ['GC=F', 'SI=F', 'HG=F', 'PL=F', 'GDX'],
        '穀物・食料・農産物': ['ZW=F', 'ZC=F', 'ZS=F', 'KC=F', 'CT=F', 'SB=F'],
        '住宅・建設': ['LBS=F'],
        '為替': ['JPY=X', 'EURUSD=X', 'CNY=X', 'CHF=X', 'GBP=X', 'AUD=X', 'DX-Y.NYB'],
        '債券・信用リスク': ['^TNX', 'TLT', 'LQD', 'HYG'],
        'リスク指標・暗号資産': ['^VIX', 'BTC-USD', '^RUT']
    };

    const commodities = ['CL=F', 'GC=F', 'SI=F', 'HG=F', 'NG=F', 'PL=F', 'ZW=F', 'ZC=F', 'ZS=F', 'KC=F', 'CT=F', 'SB=F', 'LBS=F'];
    const japanRelated = ['^N225', 'JPY=X', 'EWJ'];
    const fearGrp = ['^VIX', '^TNX', 'BTC-USD', '^RUT', 'TLT', 'LQD', 'HYG'];
    const fxGrp = ['JPY=X', 'EURUSD=X', 'CNY=X', 'DX-Y.NYB', 'CHF=X', 'GBP=X', 'AUD=X'];
    const sectorGrp = ['XLE', 'XLF', 'XLV', 'XLU', 'ITA', 'HACK', 'URA', 'GDX'];
    const emergingGrp = ['^KS11', '^BSESN', '^GSPTSE', 'EEM', 'FXI', 'EWJ'];

    Object.entries(groups).forEach(([groupName, symbols]) => {
        const groupLabel = document.createElement('div');
        groupLabel.className = 'index-group-label';
        groupLabel.textContent = groupName;
        container.appendChild(groupLabel);

        const groupRow = document.createElement('div');
        groupRow.className = 'index-group-row';

        symbols.forEach(sym => {
            const idx = stockIndices.find(i => i.id === sym);
            if (!idx) return;

            const chip = document.createElement('div');
            chip.className = 'index-chip';
            if (commodities.includes(idx.id)) chip.classList.add('commodity');
            if (japanRelated.includes(idx.id)) chip.classList.add('japan');
            if (fearGrp.includes(idx.id)) chip.classList.add('fear');
            if (fxGrp.includes(idx.id)) chip.classList.add('fx');
            if (sectorGrp.includes(idx.id)) chip.classList.add('sector');
            if (emergingGrp.includes(idx.id)) chip.classList.add('emerging');

            // 関連指標はデフォルト選択
            if (event.related_indices && event.related_indices.includes(idx.id)) {
                chip.classList.add('selected');
            }

            chip.textContent = idx.name;
            chip.dataset.symbol = idx.id;
            chip.title = idx.description;

            chip.addEventListener('click', () => {
                chip.classList.toggle('selected');
            });

            groupRow.appendChild(chip);
        });

        container.appendChild(groupRow);
    });
}

// ===== Stock Chart =====
async function loadStockChart() {
    const selected = document.querySelectorAll('.index-chip.selected');
    if (selected.length === 0) {
        alert('表示する指標を選択してください');
        return;
    }

    const margin = document.getElementById('marginDays').value;
    const chartContainer = document.getElementById('chartContainer');
    const loading = document.getElementById('chartLoading');
    chartContainer.style.display = 'block';
    loading.style.display = 'flex';

    if (stockChart) { stockChart.destroy(); stockChart = null; }

    const datasets = [];
    const colors = [
        '#4a8cff', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
        '#1abc9c', '#e67e22', '#3498db', '#e91e63', '#00bcd4'
    ];

    let colorIdx = 0;
    for (const chip of selected) {
        const symbol = chip.dataset.symbol;
        try {
            const resp = await fetch(
                `/api/stock/${encodeURIComponent(symbol)}?start=${selectedEvent.start_date}&end=${selectedEvent.end_date}&margin=${margin}`
            );
            const data = await resp.json();
            if (data.data && data.data.length > 0) {
                const color = colors[colorIdx % colors.length];
                datasets.push({
                    label: chip.textContent,
                    data: data.data.map(d => ({ x: d.date, y: d.close })),
                    borderColor: color,
                    backgroundColor: color + '20',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.1,
                    yAxisID: 'y' + colorIdx
                });
                colorIdx++;
            }
        } catch (e) {
            console.error('Error loading', symbol, e);
        }
    }

    loading.style.display = 'none';

    if (datasets.length === 0) {
        alert('データを取得できませんでした');
        return;
    }

    // 各データセットに独立したY軸を作る（最初のだけ表示、他は非表示）
    const scales = {
        x: {
            type: 'time',
            time: { unit: 'day', tooltipFormat: 'yyyy-MM-dd' },
            grid: { color: '#e8ecf0' },
            ticks: { color: '#7f8c9b' }
        }
    };

    datasets.forEach((ds, i) => {
        scales['y' + i] = {
            type: 'linear',
            display: i === 0,
            position: i % 2 === 0 ? 'left' : 'right',
            grid: { color: i === 0 ? '#e8ecf0' : 'transparent' },
            ticks: { color: ds.borderColor }
        };
    });

    const ctx = document.getElementById('stockChart').getContext('2d');
    stockChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: '#2c3e50' } },
                tooltip: {
                    backgroundColor: '#fff',
                    borderColor: '#dce1e8',
                    borderWidth: 1,
                    titleColor: '#2c3e50',
                    bodyColor: '#5a6a7a'
                },
                annotation: undefined
            },
            scales
        }
    });

    // イベント期間のハイライト（Chart.jsのプラグイン不要、背景色で代替）
    addEventAnnotation();
}

function addEventAnnotation() {
    if (!stockChart) return;
    const eventStart = selectedEvent.start_date;
    const eventEnd = selectedEvent.end_date;

    const annotations = {
        startLine: {
            type: 'line',
            xMin: eventStart, xMax: eventStart,
            borderColor: '#e74c3c',
            borderWidth: 2,
            borderDash: [5, 5],
            label: {
                display: true, content: '開始',
                position: 'start', color: '#e74c3c',
                backgroundColor: '#e74c3c20',
                font: { size: 11, weight: 'bold' },
                padding: 4
            }
        },
        endLine: {
            type: 'line',
            xMin: eventEnd, xMax: eventEnd,
            borderColor: '#2ecc71',
            borderWidth: 2,
            borderDash: [5, 5],
            label: {
                display: true, content: '終了',
                position: 'start', color: '#2ecc71',
                backgroundColor: '#2ecc7120',
                font: { size: 11, weight: 'bold' },
                padding: 4
            }
        },
        eventPeriod: {
            type: 'box',
            xMin: eventStart, xMax: eventEnd,
            backgroundColor: 'rgba(74, 140, 255, 0.05)',
            borderWidth: 0
        }
    };

    // 重要日付のマーカーを追加
    const keyDates = keyDatesData[selectedEvent.id] || [];
    const markerColors = [
        '#ff9f43', '#feca57', '#54a0ff', '#5f27cd', '#01a3a4',
        '#ff6b6b', '#48dbfb', '#ff9ff3', '#00d2d3', '#c8d6e5'
    ];

    keyDates.forEach((kd, i) => {
        const color = markerColors[i % markerColors.length];
        // 開始/終了日と同じ日はスキップ
        if (kd.date === eventStart || kd.date === eventEnd) return;

        annotations[`keyDate_${i}`] = {
            type: 'line',
            xMin: kd.date, xMax: kd.date,
            borderColor: color + '90',
            borderWidth: 1.5,
            borderDash: [3, 3],
            label: {
                display: true,
                content: kd.label,
                position: (i % 3 === 0) ? 'start' : (i % 3 === 1) ? 'center' : 'end',
                color: color,
                backgroundColor: '#ffffffe0',
                font: { size: 10 },
                padding: { top: 3, bottom: 3, left: 6, right: 6 },
                rotation: -90,
                textAlign: 'start'
            }
        };
    });

    stockChart.options.plugins.annotation = { annotations };
    stockChart.update();
}

// ===== Similar Events =====
async function loadSimilarEvents(eventId) {
    const resp = await fetch(`/api/events/similar/${eventId}`);
    const similar = await resp.json();

    const container = document.getElementById('similarEvents');
    container.innerHTML = '';

    if (similar.length === 0) {
        container.innerHTML = '<p style="color:#7f8c9b">類似のイベントが見つかりませんでした</p>';
        document.getElementById('compareControls').style.display = 'none';
        return;
    }

    const list = document.createElement('div');
    list.className = 'similar-list';

    similar.forEach(event => {
        const card = document.createElement('div');
        card.className = 'similar-card';
        card.dataset.eventId = event.id;

        const cat = categories.find(c => c.id === event.category);
        card.innerHTML = `
            <h4>${event.name}</h4>
            <div class="card-date">${event.start_date} 〜 ${event.end_date}</div>
            <div class="card-desc">${event.market_impact}</div>
            <div class="card-tags">
                ${(event.tags || []).slice(0, 4).map(t => `<span class="tag">${t}</span>`).join('')}
            </div>
        `;

        card.addEventListener('click', (e) => {
            // 類似イベントをクリックで選択/解除（比較用）
            card.classList.toggle('selected');
            const id = event.id;
            if (selectedSimilarIds.includes(id)) {
                selectedSimilarIds = selectedSimilarIds.filter(i => i !== id);
            } else {
                selectedSimilarIds.push(id);
            }
            document.getElementById('compareControls').style.display =
                selectedSimilarIds.length > 0 ? 'block' : 'none';
        });

        // ダブルクリックでそのイベントの詳細へ
        card.addEventListener('dblclick', () => showEventDetail(event));

        list.appendChild(card);
    });

    container.appendChild(list);
    document.getElementById('compareControls').style.display = 'none';
}

// ===== Compare Chart =====
async function loadCompareChart() {
    if (selectedSimilarIds.length === 0) return;

    const symbol = document.getElementById('compareIndex').value;
    const allIds = [selectedEvent.id, ...selectedSimilarIds];
    const compareContainer = document.getElementById('compareChartContainer');
    const loading = document.getElementById('compareLoading');
    compareContainer.style.display = 'block';
    loading.style.display = 'flex';

    if (compareChart) { compareChart.destroy(); compareChart = null; }

    try {
        const params = new URLSearchParams();
        allIds.forEach(id => params.append('event_ids', id));
        params.set('symbol', symbol);
        params.set('margin', '60');

        const resp = await fetch(`/api/stock/compare?${params}`);
        const results = await resp.json();

        const colors = [
            '#4a8cff', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
            '#1abc9c', '#e67e22', '#3498db'
        ];

        const datasets = results.map((r, i) => ({
            label: r.event.name + ` (${r.event.start_date.substring(0, 4)})`,
            data: r.data.map(d => ({ x: d.days_from_event, y: d.normalized })),
            borderColor: colors[i % colors.length],
            backgroundColor: 'transparent',
            borderWidth: i === 0 ? 3 : 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.1,
            borderDash: i === 0 ? [] : [5, 3]
        }));

        loading.style.display = 'none';

        const ctx = document.getElementById('compareChart').getContext('2d');
        compareChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { labels: { color: '#2c3e50' } },
                    tooltip: {
                        backgroundColor: '#fff',
                        borderColor: '#dce1e8',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => `イベント開始日から ${items[0].raw.x} 日`,
                            label: (item) => `${item.dataset.label}: ${item.raw.y > 0 ? '+' : ''}${item.raw.y.toFixed(2)}%`
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: { display: true, text: 'イベント開始日からの日数', color: '#7f8c9b' },
                        grid: { color: '#1a2040' },
                        ticks: { color: '#7f8c9b' }
                    },
                    y: {
                        title: { display: true, text: '変化率 (%)', color: '#7f8c9b' },
                        grid: { color: '#1a2040' },
                        ticks: {
                            color: '#7f8c9b',
                            callback: v => (v > 0 ? '+' : '') + v + '%'
                        }
                    }
                }
            }
        });

    } catch (e) {
        console.error('Compare error:', e);
        loading.style.display = 'none';
        alert('比較データの取得に失敗しました');
    }
}

// ===== Listeners =====
function setupListeners() {
    document.getElementById('searchInput').addEventListener('input', filterEvents);
    document.getElementById('categoryFilter').addEventListener('change', filterEvents);

    document.querySelectorAll('.era-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.era-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterEvents();
        });
    });

    document.getElementById('closeDetail').addEventListener('click', () => {
        document.getElementById('detailSection').style.display = 'none';
        selectedEvent = null;
    });

    document.getElementById('loadChart').addEventListener('click', loadStockChart);
    document.getElementById('loadCompare').addEventListener('click', loadCompareChart);
}

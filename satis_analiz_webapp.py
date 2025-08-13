from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO
from datetime import datetime

app = FastAPI()

# CORS ayarları (HTML'den veri gönderebilmek için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
    <head>
        <title>Satış Analiz Uygulaması</title>
        <meta charset="utf-8" />
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600&display=swap" rel="stylesheet">
        <style>
            body { font-family:'Montserrat',sans-serif; background:#f7f7f8; color:#05111E; padding:40px; }
            h2 { text-align:center; margin-bottom: 20px; }
            form { background:#fff; padding:20px; border-radius:12px; box-shadow:0 8px 24px rgba(0,0,0,.06); max-width: 1000px; margin: 0 auto 16px; }
            .row { display:flex; gap:16px; flex-wrap:wrap; align-items:center; }
            .row > * { flex: 1 1 220px; }
            input[type="file"], input[type="date"], button { width:100%; padding:10px 12px; border:1px solid #e5e7eb; border-radius:10px; }
            button { background:#111827; color:#fff; border:none; cursor:pointer; }
            button:hover { opacity:.9; }
            .table-wrap { background:#fff; padding:20px; border-radius:12px; box-shadow:0 8px 24px rgba(0,0,0,.06); overflow:auto; max-width: 1000px; margin: 0 auto; }
            table { width:100%; border-collapse: collapse; }
            th, td { padding:12px 14px; border-bottom:1px solid #eef0f3; text-align:left; vertical-align: middle; }
            th { background:#f3f4f6; font-weight:600; }
            .right { text-align:right; }
            .btn-mini { padding:8px 12px; border-radius:8px; background:#2563eb; color:#fff; border:none; cursor:pointer; }
            .btn-mini:hover { opacity:.9; }
            .muted { color:#6b7280; font-size: 14px; margin: 12px 0; }
            .rate-input { width: 90px; padding:6px 8px; border:1px solid #e5e7eb; border-radius:8px; }
            .controls { display:flex; gap:8px; align-items:center; justify-content:flex-end; margin-bottom:10px; }
            .controls input { width: 100px; padding:6px 8px; border:1px solid #e5e7eb; border-radius:8px; }
            .pill { background:#f3f4f6; padding:6px 10px; border-radius:999px; font-size:12px; }
            .summary { display:flex; justify-content:flex-end; margin-top:12px; }
            .summary .pill strong { font-weight:700; }
        </style>
    </head>
    <body>
        <h2>Excel Satış Analizi (Türkçe Arayüz)</h2>
        <form id="upload-form" enctype="multipart/form-data">
            <div class="row">
                <div>
                    <label>Excel Dosyası</label>
                    <input type="file" name="file" accept=".xlsx,.xls">
                </div>
                <div>
                    <label>Başlangıç Tarihi</label>
                    <input type="date" name="start_date">
                </div>
                <div>
                    <label>Bitiş Tarihi</label>
                    <input type="date" name="end_date">
                </div>
                <div style="flex:0 0 160px">
                    <label>&nbsp;</label>
                    <button type="submit">Hesapla</button>
                </div>
            </div>
        </form>

        <div class="table-wrap" id="result">
            <p class="muted">Sonuçlar burada görünecek.</p>
        </div>

        <script>
        const form = document.getElementById("upload-form");
        const resultEl = document.getElementById("result");
        const fmt = (n) => (Number(n) || 0).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        function recalcSummary() {
            // Tüm satırların oran * toplam tutarlarının toplamını hesapla
            let sum = 0;
            resultEl.querySelectorAll("tr[data-ders]").forEach(row => {
                const toplam = Number(row.dataset.toplam) || 0;
                const oran = Number(row.querySelector(".rate-input").value) || 0;
                sum += toplam * (oran/100);
            });
            const el = resultEl.querySelector("#telif-toplam");
            if (el) el.textContent = fmt(sum);
        }

        form.onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(form);

            if (!formData.get("file") || !formData.get("start_date") || !formData.get("end_date")) {
                resultEl.innerHTML = "<p>Lütfen dosya ve tarihleri seçin.</p>";
                return;
            }

            try {
                const res = await fetch("/analiz", { method: "POST", body: formData });
                if (!res.ok) throw new Error("İstek başarısız: " + res.status);
                const data = await res.json();

                // Varsayılan oran
                const defaultRate = 20;

                let html = `
                    <div class="controls">
                        <span class="pill">Genel Toplam: <strong>${fmt(data.total)}</strong> TL</span>
                        <label>Varsayılan Oran (%)</label>
                        <input type="number" id="global-rate" min="0" max="1000" step="0.01" value="${defaultRate}">
                        <button id="apply-rate" class="btn-mini" type="button">Uygula</button>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>📘 Ders</th>
                                <th class="right">Toplam Satış (TL)</th>
                                <th class="right">% Oran → Tutar (TL)</th>
                                <th>İşlem</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                for (const item of data.detaylar) {
                    const toplam = Number(item.tutar) || 0;
                    const oran = defaultRate;
                    const tutarYuzde = toplam * (oran/100);
                    const ders = (item.ders ?? "").toString().replace(/"/g, '&quot;');
                    html += `
                        <tr data-ders="${ders}" data-toplam="${toplam}">
                            <td>${ders}</td>
                            <td class="right toplam">${fmt(toplam)}</td>
                            <td class="right">
                                <input class="rate-input" type="number" min="0" max="1000" step="0.01" value="${oran}"> %
                                &rarr; <span class="rate-amount">${fmt(tutarYuzde)}</span>
                            </td>
                            <td><button class="btn-mini hesapla-btn" data-ders="${ders}">Hesapla</button></td>
                        </tr>
                    `;
                }

                html += `
                        </tbody>
                    </table>
                    <div class="summary">
                        <span class="pill">Toplam Telif Tutarı: <strong id="telif-toplam">${fmt( data.detaylar.reduce((acc,i)=>acc+(Number(i.tutar)||0)*(defaultRate/100), 0 ) )}</strong> TL</span>
                    </div>
                `;

                resultEl.innerHTML = html;

                // Satır bazında oran değişiminde hesapla + özet güncelle
                resultEl.querySelectorAll("input.rate-input").forEach(inp => {
                    inp.addEventListener("input", () => {
                        const row = inp.closest("tr");
                        const toplam = Number(row.dataset.toplam) || 0;
                        let oran = Number(inp.value);
                        if (!isFinite(oran)) oran = 0;
                        if (oran < 0) oran = 0;
                        const tutar = toplam * (oran/100);
                        row.querySelector(".rate-amount").textContent = fmt(tutar);
                        recalcSummary();
                    });
                });

                // Global oran uygula
                const applyBtn = resultEl.querySelector("#apply-rate");
                applyBtn.addEventListener("click", () => {
                    const globalRate = Number(resultEl.querySelector("#global-rate").value) || 0;
                    resultEl.querySelectorAll("tr[data-ders] .rate-input").forEach(inp => {
                        inp.value = globalRate;
                        inp.dispatchEvent(new Event("input"));
                    });
                    recalcSummary();
                });

                // "Hesapla" -> yeni sekmede aylık döküm aç
                resultEl.querySelectorAll(".hesapla-btn").forEach(btn => {
                    btn.addEventListener("click", (ev) => {
                        ev.preventDefault();

                        const row = btn.closest("tr");
                        const ders = btn.getAttribute("data-ders");
                        const oran = Number(row.querySelector(".rate-input").value) || 0;

                        // Aynı dosya + tarihleri tekrar göndererek yeni sekmede açıyoruz
                        const tempForm = document.createElement("form");
                        tempForm.method = "POST";
                        tempForm.enctype = "multipart/form-data";
                        tempForm.action = "/aylik-dokum";
                        tempForm.target = "_blank";

                        // Orijinal formdaki alanları kopyala
                        const fd = new FormData(form);
                        for (const [k,v] of fd.entries()) {
                            if (v instanceof File) {
                                const fileInput = document.createElement("input");
                                fileInput.type = "file";
                                fileInput.name = k;
                                // Not: File nesnesini programatik olarak yeniden set etmek mümkün değil.
                                // Bunun için aşağıdaki workaround: mevcut input elementini klonlayıp forma ekleyelim.
                                // Basit yol: doğrudan orijinal input'u formun içine taşıyıp sonra geri koymak.
                            }
                        }

                        // Pratik çözüm: gizli inputlar ile tarihleri ve ders/oranı ekleyip,
                        // dosya input'unu da DOM'dan kopyalayıp bu forma clone ederek ekleyeceğiz.
                        // (Tarayıcılar programatik File set etmeye izin vermez.)
                        const originalFileInput = form.querySelector('input[type="file"][name="file"]');
                        if (!originalFileInput || !originalFileInput.files || originalFileInput.files.length === 0) {
                            alert("Lütfen dosyayı yeniden seçin.");
                            return;
                        }

                        // Yeni form içine bir file input kopyası koy
                        const fileClone = originalFileInput.cloneNode();
                        // Kullanıcı etkileşimi olmadan File listesini aktaramayız; bu yüzden
                        // yeni bir FormData üzerinden submit gerekiyor. Bunun için iframe/target
                        // yaklaşımında file'ı yeniden seçmek gerekir. Basit ve çalışır yöntem:
                        // Geçici bir form yaratıp orijinal input'u bu forma move et, submit et, sonra geri koy.
                        const placeholder = document.createElement("span");
                        originalFileInput.parentNode.insertBefore(placeholder, originalFileInput);
                        tempForm.appendChild(originalFileInput); // inputu geçici forma taşı
                        
                        // Diğer alanlar
                        const addHidden = (name, value) => {
                            const inp = document.createElement("input");
                            inp.type = "hidden";
                            inp.name = name;
                            inp.value = value;
                            tempForm.appendChild(inp);
                        };
                        addHidden("start_date", form.querySelector('input[name="start_date"]').value);
                        addHidden("end_date", form.querySelector('input[name="end_date"]').value);
                        addHidden("ders", ders);
                        addHidden("rate", oran.toString());

                        document.body.appendChild(tempForm);
                        tempForm.submit();

                        // File input'u eski yerine geri koy
                        placeholder.parentNode.insertBefore(originalFileInput, placeholder);
                        placeholder.remove();
                        tempForm.remove();
                    });
                });

            } catch (err) {
                console.error(err);
                resultEl.innerHTML = "<p>Bir hata oluştu. Lütfen dosya sütunlarını ve tarih aralığını kontrol edin.</p>";
            }
        };
        </script>
    </body>
    </html>
    """

@app.post("/analiz")
async def analiz(file: UploadFile = File(...), start_date: str = Form(...), end_date: str = Form(...)):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    # Gerekli sütunların temizlenmesi
    df = df[['Tarih', 'Ders', 'Tutar']]
    df['Tarih'] = pd.to_datetime(df['Tarih'])

    # Tarih filtreleme
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    mask = (df['Tarih'] >= start) & (df['Tarih'] <= end)
    filtered = df.loc[mask]

    total_sales = filtered['Tutar'].sum()
    grouped = filtered.groupby('Ders')['Tutar'].sum().reset_index()
    detaylar = grouped.to_dict(orient='records')

    return {
        "total": float(total_sales),
        "detaylar": [{"ders": row['Ders'], "tutar": float(row['Tutar'])} for row in detaylar]
    }

@app.post("/aylik-dokum", response_class=HTMLResponse)
async def aylik_dokum(
    file: UploadFile = File(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    ders: str = Form(...),
    rate: float = Form(...),
    rates: str = Form(None)
):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    df = df[['Tarih', 'Ders', 'Tutar']]
    df['Tarih'] = pd.to_datetime(df['Tarih'], errors='coerce')
    df = df.dropna(subset=['Tarih'])
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    base = df[(df['Tarih'] >= start) & (df['Tarih'] <= end)].copy()

    try:
        rates_map = json.loads(rates) if rates else {}
    except Exception:
        rates_map = {}

    include_dersler = [str(ders)]
    tum_dersler = sorted(set(base['Ders'][base['Ders'].astype(str).str.startswith('Tüm')].astype(str)))
    include_dersler.extend([d for d in tum_dersler if d not in include_dersler])

    monthly_frames = []
    for dname in include_dersler:
        sub = base[base['Ders'].astype(str) == dname].copy()
        if sub.empty:
            continue
        sub['Ay'] = sub['Tarih'].dt.to_period('M').astype(str)
        grp = (sub.groupby('Ay', as_index=False)
                  .agg(Toplam=('Tutar','sum'), IslemAdedi=('Tutar','size')))
        d_rate = float(rates_map.get(dname, rate))
        grp['Ders'] = dname
        grp['Oran'] = d_rate
        monthly_frames.append(grp)

    if not monthly_frames:
        return HTMLResponse(content=wrap_html(
            "<p style='font-family:Montserrat,sans-serif'>Seçilen aralıkta kayıt bulunamadı.</p>",
            title="Aylık Döküm",
            add_pdf_scripts=True
        ))

    monthly_all = pd.concat(monthly_frames, ignore_index=True).sort_values(['Ay','Ders'])

    def fmt(n):
        try:
            return f"{float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00"

    rows_html = []
    for _, row in monthly_all.iterrows():
        rows_html.append(
            f"<tr data-ay='{escape_html(row.Ay)}' "
            f"data-ders='{escape_html(row.Ders)}' "
            f"data-toplam='{float(row.Toplam):.6f}'>"
            f"<td>{escape_html(row.Ay)}</td>"
            f"<td>{escape_html(row.Ders)}</td>"
            f"<td class='right'>{fmt(row.Toplam)}</td>"
            f"<td class='right'>{int(row.IslemAdedi)}</td>"
            f"<td class='right'>"
            f"  <input class='rate-input' type='number' min='0' max='1000' step='0.01' value='{float(row.Oran):.2f}'> %"
            f"  &rarr; <span class='telif-cell'></span>"
            f"</td>"
            f"</tr>"
        )
    table_rows = "\n".join(rows_html)

    body = f"""
    <div class="head">
        <h2>Flu Akademi Dönemlik Ders Bazlı Satış Dökümü</h2>
        <div class="info">
            <div><strong>Seçilen Ders:</strong> {escape_html(ders)}</div>
            <div><strong>Tarih Aralığı:</strong> {start_date} → {end_date}</div>
            <div><strong>Not:</strong> Flu Akademi Eğitmen Telif Tablosu</div>
        </div>
        <div class="actions">
            <label>Varsayılan Oran (%)</label>
            <input id="global-rate" type="number" min="0" max="1000" step="0.01" value="{float(rate):.2f}">
            <button id="apply-rate">Tüm Satırlara Uygula</button>
            <button id="pdfBtn">PDF Olarak İndir</button>
        </div>
    </div>

    <table id="reportTable">
        <thead>
            <tr>
                <th>Ay</th>
                <th>Ders</th>
                <th class="right">Toplam Satış (TL)</th>
                <th class="right">İşlem Adedi</th>
                <th class="right">Oran (%) → Telif (TL)</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
        <tfoot>
            <tr>
                <th>Genel</th>
                <th>—</th>
                <th class="right" id="genel-toplam">0,00</th>
                <th class="right" id="genel-islem">0</th>
                <th class="right" id="genel-telif">0,00</th>
            </tr>
        </tfoot>
    </table>

    <script>
        const fmt = (n) => (Number(n)||0).toLocaleString('tr-TR', {{ minimumFractionDigits:2, maximumFractionDigits:2 }});

        function recalc() {{
            let sumToplam = 0, sumIslem = 0, sumTelif = 0;

            document.querySelectorAll('#reportTable tbody tr').forEach(tr => {{
                const toplam = Number(tr.dataset.toplam) || 0;
                sumToplam += toplam;

                const islem = Number(tr.children[3].textContent.trim()) || 0;
                sumIslem += islem;

                const rateInp = tr.querySelector('.rate-input');
                let oran = Number(rateInp.value) || 0;
                if (!isFinite(oran) || oran < 0) oran = 0;

                const dersKey = tr.dataset.ders;
                const ayKey = tr.dataset.ay;
                localStorage.setItem(`oran_${{dersKey}}_${{ayKey}}`, oran);

                const telif = toplam * (oran / 100);
                tr.querySelector('.telif-cell').textContent = fmt(telif);
                sumTelif += telif;
            }});

            document.getElementById('genel-toplam').textContent = fmt(sumToplam);
            document.getElementById('genel-islem').textContent = sumIslem.toString();
            document.getElementById('genel-telif').textContent = fmt(sumTelif);
        }}

        document.querySelectorAll('#reportTable tbody tr').forEach(tr => {{
            const dersKey = tr.dataset.ders;
            const ayKey = tr.dataset.ay;
            const savedRate = localStorage.getItem(`oran_${{dersKey}}_${{ayKey}}`);
            if (savedRate !== null) {{
                tr.querySelector('.rate-input').value = savedRate;
            }}
        }});

        recalc();

        document.querySelectorAll('.rate-input').forEach(inp => {{
            inp.addEventListener('input', recalc);
        }});

        document.getElementById('apply-rate').addEventListener('click', () => {{
            const g = Number(document.getElementById('global-rate').value) || 0;
            document.querySelectorAll('.rate-input').forEach(inp => {{
                inp.value = g;
            }});
            recalc();
        }});

        const {{ jsPDF }} = window.jspdf || {{}};
        document.getElementById('pdfBtn').addEventListener('click', () => {{
            const doc = new jsPDF();
            doc.text("Flu Akademi Dönemlik Ders Bazlı Satış Dökümü", 14, 16);

            const head = [["Ay","Ders","Toplam Satış (TL)","İşlem Adedi","Telif (TL)"]];
            const body = Array.from(document.querySelectorAll('#reportTable tbody tr')).map(tr => {{
                const ay = tr.children[0].textContent.trim();
                const ders = tr.children[1].textContent.trim();
                const toplam = tr.children[2].textContent.trim();
                const islem = tr.children[3].textContent.trim();
                const telif = tr.querySelector('.telif-cell').textContent.trim();
                return [ay, ders, toplam, islem, telif];
            }});
            const foot = [[
                "Genel","—",
                document.getElementById('genel-toplam').textContent.trim(),
                document.getElementById('genel-islem').textContent.trim(),
                document.getElementById('genel-telif').textContent.trim()
            ]];

            doc.autoTable({{
                head, body, foot,
                startY: 22,
                styles: {{ halign: 'right' }},
                headStyles: {{ halign: 'right' }},
                columnStyles: {{ 0: {{halign: 'left'}}, 1: {{halign: 'left'}} }}
            }});
            doc.save("aylik_dokum.pdf");
        }});
    </script>
    """

    return HTMLResponse(content=wrap_html(body, title="Aylık Döküm", add_pdf_scripts=True))



    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    # Kolonlar ve tarih filtresi
    df = df[['Tarih', 'Ders', 'Tutar']]
    df['Tarih'] = pd.to_datetime(df['Tarih'], errors='coerce')
    df = df.dropna(subset=['Tarih'])
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    base = df[(df['Tarih'] >= start) & (df['Tarih'] <= end)].copy()

    # Dashboard’tan gelen oranlar
    try:
        rates_map = json.loads(rates) if rates else {}
    except Exception:
        rates_map = {}

    # Dahil edilecek dersler: tıklanan + "Tüm" ile başlayanlar
    include_dersler = [str(ders)]
    tum_dersler = sorted(set(base['Ders'][base['Ders'].astype(str).str.startswith('Tüm')].astype(str)))
    include_dersler.extend([d for d in tum_dersler if d not in include_dersler])

    # Her ders için ay-ay grupla (Ay + Ders + Toplam + IslemAdedi + Oran)
    monthly_frames = []
    for dname in include_dersler:
        sub = base[base['Ders'].astype(str) == dname].copy()
        if sub.empty:
            continue
        sub['Ay'] = sub['Tarih'].dt.to_period('M').astype(str)
        grp = (sub.groupby('Ay', as_index=False)
                  .agg(Toplam=('Tutar','sum'), IslemAdedi=('Tutar','size')))
        d_rate = float(rates_map.get(dname, rate))  # dashboardtaki oran varsa onu kullan
        grp['Ders'] = dname
        grp['Oran'] = d_rate
        monthly_frames.append(grp)

    if not monthly_frames:
        return HTMLResponse(content=wrap_html(
            f"<p style='font-family:Montserrat,sans-serif'>Seçilen aralıkta kayıt bulunamadı.</p>",
            title="Aylık Döküm",
            add_pdf_scripts=True
        ))

    monthly_all = pd.concat(monthly_frames, ignore_index=True).sort_values(['Ay','Ders'])

    # Satırları oluştur (Telif JS tarafından oran değişince dinamik hesaplanacak)
    def fmt(n):
        try:
            return f"{float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00"

    rows_html = []
    for _, row in monthly_all.iterrows():
        rows_html.append(
            f"<tr data-ay='{escape_html(row.Ay)}' "
            f"data-ders='{escape_html(row.Ders)}' "
            f"data-toplam='{float(row.Toplam):.6f}'>"
            f"<td>{escape_html(row.Ay)}</td>"
            f"<td>{escape_html(row.Ders)}</td>"
            f"<td class='right'>{fmt(row.Toplam)}</td>"
            f"<td class='right'>{int(row.IslemAdedi)}</td>"
            f"<td class='right'>"
            f"  <input class='rate-input' type='number' min='0' max='1000' step='0.01' value='{float(row.Oran):.2f}'> %"
            f"  &rarr; <span class='telif-cell'></span>"
            f"</td>"
            f"</tr>"
        )
    table_rows = "\n".join(rows_html)

    # Sayfa gövdesi (Oran değişince footer ve hücreler canlı güncellenir)
    body = f"""
    <div class="head">
        <h2>Flu Akademi Dönemlik Ders Bazlı Satış Dökümü</h2>
        <div class="info">
            <div><strong>Seçilen Ders:</strong> {escape_html(ders)}</div>
            <div><strong>Tarih Aralığı:</strong> {start_date} → {end_date}</div>
            <div><strong>Not:</strong> Flu Akademi Eğitmen Telif Tablosu</div>
        </div>
        <div class="actions">
            <label>Varsayılan Oran (%)</label>
            <input id="global-rate" type="number" min="0" max="1000" step="0.01" value="{float(rate):.2f}">
            <button id="apply-rate">Tüm Satırlara Uygula</button>
        </div>
    </div>

    <table id="reportTable">
        <thead>
            <tr>
                <th>Ay</th>
                <th>Ders</th>
                <th class="right">Toplam Satış (TL)</th>
                <th class="right">İşlem Adedi</th>
                <th class="right">Oran (%) → Telif (TL)</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
        <tfoot>
            <tr>
                <th>Genel</th>
                <th>—</th>
                <th class="right" id="genel-toplam">0,00</th>
                <th class="right" id="genel-islem">0</th>
                <th class="right" id="genel-telif">0,00</th>
            </tr>
        </tfoot>
    </table>

    <script>
        const fmt = (n) => (Number(n)||0).toLocaleString('tr-TR', {{minimumFractionDigits:2, maximumFractionDigits:2}});

        function recalc() {{
            let sumToplam = 0, sumIslem = 0, sumTelif = 0;

            document.querySelectorAll('#reportTable tbody tr').forEach(tr => {{
                const toplam = Number(tr.dataset.toplam) || 0;
                sumToplam += toplam;

                const islem = Number(tr.children[3].textContent.trim()) || 0;
                sumIslem += islem;

                const rateInp = tr.querySelector('.rate-input');
                let oran = Number(rateInp.value) || 0;
                if (!isFinite(oran) || oran < 0) oran = 0;

                // localStorage'a kaydet
                const dersKey = tr.dataset.ders;
                const ayKey = tr.dataset.ay;
                localStorage.setItem(`oran_${dersKey}_${ayKey}`, oran);

                const telif = toplam * (oran / 100);
                tr.querySelector('.telif-cell').textContent = fmt(telif);
                sumTelif += telif;
            }});

            document.getElementById('genel-toplam').textContent = fmt(sumToplam);
            document.getElementById('genel-islem').textContent = sumIslem.toString();
            document.getElementById('genel-telif').textContent = fmt(sumTelif);
        }}

        
        // Başlangıçta hesapla
        recalc();

        // Satır oranları değiştikçe canlı hesap
        document.querySelectorAll('.rate-input').forEach(inp => {{
            inp.addEventListener('input', recalc);
        }});

        // Global oran uygula
        document.getElementById('apply-rate').addEventListener('click', () => {{
            const g = Number(document.getElementById('global-rate').value)||0;
            document.querySelectorAll('.rate-input').forEach(inp => {{
                inp.value = g;
            }});
            recalc();
        }});

        // PDF export (güncel değerleri okur)
        const {{ jsPDF }} = window.jspdf || {{}};
        document.getElementById('pdfBtn').addEventListener('click', () => {{
            const doc = new jsPDF();
            doc.text("Flu Akademi Dönemlik Ders Bazlı Satış Dökümü", 14, 16);

            const head = [["Ay","Ders","Toplam Satış (TL)","İşlem Adedi","Telif (TL)"]];
            const body = Array.from(document.querySelectorAll('#reportTable tbody tr')).map(tr => {{
                const ay = tr.children[0].textContent.trim();
                const ders = tr.children[1].textContent.trim();
                const toplam = tr.children[2].textContent.trim();
                const islem = tr.children[3].textContent.trim();
                const telif = tr.querySelector('.telif-cell').textContent.trim();
                return [ay, ders, toplam, islem, telif];
            }});
            const foot = [[
                "Genel","—",
                document.getElementById('genel-toplam').textContent.trim(),
                document.getElementById('genel-islem').textContent.trim(),
                document.getElementById('genel-telif').textContent.trim()
            ]];

            doc.autoTable({{
                head, body, foot,
                startY: 22,
                styles: {{ halign: 'right' }},
                headStyles: {{ halign: 'right' }},
                columnStyles: {{ 0: {{halign: 'left'}}, 1: {{halign: 'left'}} }}
            }});
            doc.save("aylik_dokum.pdf");
        }});
    </script>
    """

    return HTMLResponse(content=wrap_html(body, title="Aylık Döküm", add_pdf_scripts=True))

def escape_html(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def wrap_html(inner, title="Rapor", add_pdf_scripts=False):
    pdf_scripts = """
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
    """ if add_pdf_scripts else ""

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>
            body {{ font-family: Montserrat, Arial, sans-serif; background:#f7f7f8; color:#05111E; padding: 30px; }}
            .head {{ display:flex; flex-wrap:wrap; gap:16px; align-items:flex-end; justify-content:space-between; margin-bottom:14px; }}
            .info {{ display:grid; gap:4px; min-width:260px; }}
            .actions {{ display:flex; gap:8px; align-items:center; }}
            .actions input {{ width:120px; padding:8px 10px; border:1px solid #e5e7eb; border-radius:10px; }}
            .actions button {{ background:#111827; color:#fff; padding:10px 12px; border:none; border-radius:10px; cursor:pointer; }}
            .actions button:hover {{ opacity:.9; }}
            table {{ width:100%; background:#fff; border-collapse: collapse; border-radius:12px; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,.06); }}
            th, td {{ padding:12px 14px; border-bottom:1px solid #eef0f3; }}
            th {{ background:#f3f4f6; text-align:left; }}
            .right {{ text-align:right; }}
            .rate-input {{ width:90px; padding:6px 8px; border:1px solid #e5e7eb; border-radius:8px; }}
            tfoot th {{ background:#f9fafb; }}
        </style>
    </head>
    <body>
        {inner}
        {pdf_scripts}
    </body>
    </html>
    """

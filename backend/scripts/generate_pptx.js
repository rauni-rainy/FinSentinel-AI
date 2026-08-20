const PptxGenJS = require("pptxgenjs");
const fs = require("fs");

async function generate() {
    const jsonPath = process.argv[2];
    const outPath = process.argv[3];
    
    if (!jsonPath || !outPath) {
        console.error("Usage: node generate_pptx.js <input_json> <output_pptx>");
        process.exit(1);
    }

    const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
    const pres = new PptxGenJS();
    
    // Global Config
    pres.layout = "LAYOUT_16x9";
    const COLOR_NAVY = "003366";
    const COLOR_RED = "B22222";
    const COLOR_GREEN = "006633";
    const COLOR_BG = "F5F7FA";
    const COLOR_WHITE = "FFFFFF";
    
    // SLIDE 1: Executive Summary
    const s1 = pres.addSlide();
    s1.background = { color: COLOR_BG };
    s1.addText("Executive Summary", { x: 0.5, y: 0.5, w: "90%", h: 0.5, fontSize: 32, bold: true, color: COLOR_NAVY });
    
    const cardY = 1.5;
    const cardW = 2.8;
    const cardH = 1.5;
    
    const kpis = [
        { label: "Cases Analyzed", val: data.kpis.cases_analyzed.toString() },
        { label: "Model Precision", val: data.kpis.precision },
        { label: "False Positive Rate", val: data.kpis.fpr }
    ];
    
    kpis.forEach((kpi, idx) => {
        const startX = 0.5 + (idx * 3.1);
        s1.addShape(pres.ShapeType.rect, { x: startX, y: cardY, w: cardW, h: cardH, fill: { color: COLOR_WHITE }, shadow: { type: "outer", color: "666666", blur: 5, offset: 3, angle: 45, opacity: 0.2 } });
        s1.addText(kpi.val, { x: startX, y: cardY + 0.1, w: cardW, h: 0.8, fontSize: 40, bold: true, color: COLOR_NAVY, align: "center" });
        s1.addText(kpi.label, { x: startX, y: cardY + 0.9, w: cardW, h: 0.4, fontSize: 14, color: "666666", align: "center" });
    });

    // SLIDE 2: Fraud Typology Distribution (NEW)
    const s2 = pres.addSlide();
    s2.background = { color: COLOR_BG };
    s2.addText("Fraud Typology Distribution", { x: 0.5, y: 0.5, w: "90%", h: 0.5, fontSize: 32, bold: true, color: COLOR_NAVY });

    if (data.typologies && data.typologies.length > 0) {
        let chartData = [{
            name: "Typologies",
            labels: data.typologies.map(t => t.name),
            values: data.typologies.map(t => t.count)
        }];
        
        s2.addChart(pres.ChartType.bar, chartData, {
            x: 1.0, y: 1.5, w: 8.0, h: 3.5,
            barDir: "col",
            showValue: true,
            chartColors: [COLOR_NAVY, COLOR_RED, COLOR_GREEN, "F59E0B"],
            catAxisLabelColor: "333333",
            catAxisLabelFontSize: 12,
            valAxisLabelColor: "333333",
            title: "Distribution of Detected Typologies",
            showTitle: false
        });
    } else {
        s2.addText("No typologies detected in this batch.", { x: 0.5, y: 2.0, w: 9.0, h: 1.0, fontSize: 24, color: "666666", align: "center" });
    }

    // SLIDE 3+: High-Risk Escalations (Paginated)
    if (data.flagged_cases && data.flagged_cases.length > 0) {
        const CASES_PER_SLIDE = 3;
        for (let i = 0; i < data.flagged_cases.length; i += CASES_PER_SLIDE) {
            const chunk = data.flagged_cases.slice(i, i + CASES_PER_SLIDE);
            
            const s3 = pres.addSlide();
            s3.background = { color: COLOR_BG };
            s3.addText(`High-Risk Escalations (Part ${Math.floor(i / CASES_PER_SLIDE) + 1})`, { x: 0.5, y: 0.5, w: "90%", h: 0.5, fontSize: 32, bold: true, color: COLOR_RED });
            
            chunk.forEach((c, idx) => {
                const cardY2 = 1.5 + (idx * 1.5);
                
                s3.addShape(pres.ShapeType.rect, { x: 0.5, y: cardY2, w: 9.0, h: 1.2, fill: { color: COLOR_WHITE }, shadow: { type: "outer", blur: 3, opacity: 0.15 } });
                
                s3.addText(`Case: ${c.case_id} | Account: ${c.account}`, { x: 0.7, y: cardY2 + 0.1, w: 4.0, h: 0.3, fontSize: 14, bold: true, color: COLOR_NAVY });
                s3.addText(`Amount: $${c.amount}`, { x: 5.0, y: cardY2 + 0.1, w: 2.0, h: 0.3, fontSize: 14, bold: true, color: COLOR_NAVY });
                
                let confDisplay = c.confidence;
                if (typeof confDisplay === "number") confDisplay = (confDisplay * 100).toFixed(1) + "%";
                let riskDisplay = c.risk_score;
                if (typeof riskDisplay === "number") riskDisplay = (riskDisplay * 100).toFixed(0);
                
                s3.addText(`Risk: ${riskDisplay} | Conf: ${confDisplay}`, { x: 7.0, y: cardY2 + 0.1, w: 2.0, h: 0.3, fontSize: 12, color: "888888" });
                
                s3.addText(
                    [{ text: `Reason: ${c.reason}`, options: { bullet: true } }],
                    { x: 0.7, y: cardY2 + 0.5, w: 8.0, h: 0.4, fontSize: 14, color: "333333" }
                );
            });
        }
    } else {
        const s3 = pres.addSlide();
        s3.background = { color: COLOR_BG };
        s3.addText("High-Risk Escalations", { x: 0.5, y: 0.5, w: "90%", h: 0.5, fontSize: 32, bold: true, color: COLOR_RED });
        s3.addText("No cases escalated beyond ambient thresholds.", { x: 0.5, y: 2.0, w: 9.0, h: 1.0, fontSize: 24, color: "666666", align: "center" });
    }

    // SLIDE 4: Adversarial Red-Team Benchmark (NEW)
    const s4 = pres.addSlide();
    s4.background = { color: COLOR_BG };
    s4.addText("System Vulnerability: Red Team Benchmark", { x: 0.5, y: 0.5, w: "90%", h: 0.5, fontSize: 32, bold: true, color: COLOR_NAVY });
    
    if (data.redteam) {
        s4.addShape(pres.ShapeType.rect, { x: 0.5, y: 1.5, w: 9.0, h: 3.5, fill: { color: COLOR_WHITE }, shadow: { type: "outer", blur: 3, opacity: 0.15 } });
        
        s4.addText("Structuring Evasion Decay Test", { x: 1.0, y: 1.8, w: 8.0, h: 0.5, fontSize: 20, bold: true, color: COLOR_NAVY });
        s4.addText("The adversary split a single $30k fraudulent transfer into 30 micro-transactions of $1k each.", { x: 1.0, y: 2.4, w: 8.0, h: 0.3, fontSize: 14, color: "333333" });
        
        let baseline = (data.redteam.baseline_conf * 100).toFixed(1) + "%";
        let evasion = (data.redteam.evasion_conf * 100).toFixed(1) + "%";
        
        s4.addText([{ text: `Baseline Detection Confidence: `, options: { color: "666666" } }, { text: baseline, options: { color: COLOR_GREEN, bold: true } }], { x: 1.0, y: 3.0, w: 8.0, h: 0.4, fontSize: 18 });
        s4.addText([{ text: `Evasion Variant (V5) Confidence: `, options: { color: "666666" } }, { text: evasion, options: { color: COLOR_RED, bold: true } }], { x: 1.0, y: 3.5, w: 8.0, h: 0.4, fontSize: 18 });
        
        s4.addText("Insight: The statistical classifier is blind to aggregate micro-structuring. Recommendation: Implement a 24-hour rolling velocity sum.", { x: 1.0, y: 4.2, w: 8.0, h: 0.5, fontSize: 14, italic: true, color: "666666" });
    } else {
        s4.addText("No Red Team simulation artifact found. Run the simulation to populate benchmark data.", { x: 0.5, y: 2.0, w: 9.0, h: 1.0, fontSize: 20, color: "666666", align: "center" });
    }

    // SLIDE 5+: Recommended Actions (paginated to avoid overflow)
    const ACTIONS_PER_SLIDE = 4;
    const actions = (data.actions && data.actions.length > 0)
        ? data.actions
        : ["Review the flagged manual cases in the attached spreadsheet."];

    for (let ai = 0; ai < actions.length; ai += ACTIONS_PER_SLIDE) {
        const chunk = actions.slice(ai, ai + ACTIONS_PER_SLIDE);
        const pageNum = Math.floor(ai / ACTIONS_PER_SLIDE) + 1;
        const totalPages = Math.ceil(actions.length / ACTIONS_PER_SLIDE);

        const s5 = pres.addSlide();
        s5.background = { color: COLOR_BG };

        const titleSuffix = totalPages > 1 ? ` (${pageNum}/${totalPages})` : "";
        s5.addText(`Recommended Actions${titleSuffix}`, {
            x: 0.5, y: 0.3, w: "90%", h: 0.6,
            fontSize: 32, bold: true, color: COLOR_GREEN
        });

        // Background card — tall enough to hold 4 bullets at 16pt comfortably
        s5.addShape(pres.ShapeType.rect, {
            x: 0.5, y: 1.2, w: 9.0, h: 4.5,
            fill: { color: COLOR_WHITE },
            shadow: { type: "outer", blur: 3, opacity: 0.15 }
        });

        const actionBullets = chunk.map(act => ({
            text: String(act),
            options: { bullet: true, fontSize: 16, color: "333333", breakLine: true, paraSpaceAfter: 6 }
        }));

        s5.addText(actionBullets, {
            x: 0.8, y: 1.4, w: 8.4, h: 4.1,
            valign: "top"
        });
    }

    // Export
    await pres.writeFile({ fileName: outPath });
}

generate().catch(err => {
    console.error(err);
    process.exit(1);
});

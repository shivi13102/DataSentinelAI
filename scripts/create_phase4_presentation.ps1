$ErrorActionPreference = 'Stop'

function Color([int]$r, [int]$g, [int]$b) {
    return [int]($r + 256 * $g + 65536 * $b)
}

function AddText(
    $slide,
    [string]$text,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [int]$size,
    [int]$color,
    [bool]$bold = $false
) {
    $shape = $slide.Shapes.AddTextbox(1, $x, $y, $w, $h)
    $shape.TextFrame.MarginLeft = 0
    $shape.TextFrame.MarginRight = 0
    $shape.TextFrame.MarginTop = 0
    $shape.TextFrame.MarginBottom = 0
    $shape.TextFrame.WordWrap = -1
    $range = $shape.TextFrame.TextRange
    $range.Text = $text
    $range.Font.Name = 'Aptos'
    $range.Font.Size = $size
    $range.Font.Bold = [int]$bold
    $range.Font.Color.RGB = $color
    return $shape
}

function AddRect(
    $slide,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [int]$fill,
    [int]$line = -1
) {
    $shape = $slide.Shapes.AddShape(1, $x, $y, $w, $h)
    $shape.Fill.Solid()
    $shape.Fill.ForeColor.RGB = $fill
    if ($line -lt 0) {
        $line = $fill
    }
    $shape.Line.ForeColor.RGB = $line
    return $shape
}

function AddBase($presentation, [int]$page, [string]$kicker, [string]$title, [string]$subtitle) {
    $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, 12)
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = Color 11 18 32
    AddRect $slide 0 0 0.12 7.5 (Color 34 211 238) | Out-Null
    AddText $slide 'DATASENTINEL AI' 0.55 0.32 3.0 0.3 12 (Color 34 211 238) $true | Out-Null
    AddText $slide $kicker.ToUpper() 0.58 0.82 11.8 0.25 10 (Color 148 163 184) $true | Out-Null
    AddText $slide $title 0.55 1.15 12.0 0.7 30 (Color 248 250 252) $true | Out-Null
    AddText $slide $subtitle 0.58 1.94 12.0 0.55 15 (Color 203 213 225) | Out-Null
    AddText $slide ('LOCAL DEMO  /  {0:00}' -f $page) 10.1 7.12 2.7 0.2 9 (Color 100 116 139) | Out-Null
    return $slide
}

function AddCard(
    $slide,
    [string]$heading,
    [string]$body,
    [double]$x,
    [double]$y,
    [double]$w,
    [double]$h,
    [int]$accent
) {
    AddRect $slide $x $y $w $h (Color 17 29 48) (Color 37 53 73) | Out-Null
    AddRect $slide ($x + 0.18) ($y + 0.2) 0.06 ($h - 0.4) $accent | Out-Null
    AddText $slide $heading ($x + 0.4) ($y + 0.22) ($w - 0.65) 0.34 16 (Color 248 250 252) $true | Out-Null
    AddText $slide $body ($x + 0.4) ($y + 0.68) ($w - 0.65) ($h - 0.85) 13 (Color 203 213 225) | Out-Null
}

$slides = @(
    @{
        Kicker = 'The guardrail before downstream'
        Title = 'A deterministic data-quality gate'
        Subtitle = 'Explainable protection before downstream processing.'
        Cards = @(
            @('MEASURE', 'Compare current data against a baseline.'),
            @('DECIDE', 'Only a consistent ALLOW can proceed.'),
            @('EXPLAIN', 'AI is optional and advisory.')
        )
    },
    @{
        Kicker = 'The problem'
        Title = 'Bad data can look like a successful run.'
        Subtitle = 'Silent shifts can propagate into reports, models, and downstream systems.'
        Cards = @(
            @('Detect meaningful change', 'Schema, missingness, duplicates, numeric drift, and categorical drift.'),
            @('Make a measurable decision', 'Findings and severity are computed by deterministic Python analysis.'),
            @('Keep the boundary clear', 'The language model does not set policy or authorize processing.')
        )
    },
    @{
        Kicker = 'How it works'
        Title = 'A simple, enforceable decision boundary.'
        Subtitle = 'Upload or fixture -> measure -> gate -> conditionally process -> report.'
        Cards = @(
            @('01  ANALYZE', 'Run detectors on baseline and current CSVs.'),
            @('02  GATE', 'ALLOW / REVIEW_REQUIRED / BLOCK from measured findings.'),
            @('03  ENFORCE', 'Simulated downstream runs only for ALLOW; AI stays advisory.')
        )
    },
    @{
        Kicker = 'Protection outcomes'
        Title = 'Three outcomes. One downstream rule.'
        Subtitle = 'A completed analysis is not the same as permission to continue.'
        Cards = @(
            @('ALLOW - Continue', 'Healthy, consistent result. Simulated downstream step may execute.'),
            @('REVIEW_REQUIRED - Hold', 'Medium-risk result. Downstream remains blocked; approval is not implemented.'),
            @('BLOCK - Stop', 'High/critical or untrustworthy result. Downstream remains blocked.')
        )
    },
    @{
        Kicker = 'Live demonstration'
        Title = 'Three fixture runs make policy visible.'
        Subtitle = 'Tracked, reproducible CSV pairs under tests/fixtures/protection/.'
        Cards = @(
            @('HEALTHY', 'No findings -> ALLOW -> simulated downstream executes.'),
            @('SUSPICIOUS', 'Missing values -> REVIEW_REQUIRED -> downstream withheld.'),
            @('CRITICAL', 'Removed column -> BLOCK -> downstream withheld.')
        )
    },
    @{
        Kicker = 'Experiment Lab'
        Title = 'Inject. Observe. Correct. Verify.'
        Subtitle = 'A controlled experiment runs against an isolated dataset copy.'
        Cards = @(
            @('Six controlled scenarios', 'Missing values, duplicates, schema, numeric drift, categorical drift, combined.'),
            @('Real measured outcome', 'Actual detectors and the same protection gate report findings.'),
            @('Targeted recovery check', 'Correction creates a recovered copy and checks the target finding again.')
        )
    },
    @{
        Kicker = 'Honest implementation status'
        Title = 'What works today - and what does not.'
        Subtitle = 'Phase 4 materials describe the checkout as it is, not a roadmap as shipped.'
        Cards = @(
            @('IMPLEMENTED', 'Detectors + gate; monitored runs + SSE; reports; branched graph; Experiment Lab.'),
            @('NOT IMPLEMENTED', 'General lineage; governed baselines; investigation graph; reviewer approval/release; durable incident history.'),
            @('DEMO BOUNDARIES', 'Single-process run state; local experiment storage; simulated downstream; no auth or production connector.')
        )
    },
    @{
        Kicker = 'The takeaway'
        Title = 'A deterministic gate. A human-readable explanation.'
        Subtitle = 'The model can help explain the evidence. It cannot overrule the evidence.'
        Cards = @(
            @('LOCAL DEMO READY', 'Show healthy, suspicious, critical, and one Experiment Lab recovery.'),
            @('CI STATUS', 'Python tests and frontend build pass locally. Jenkins/hosted Actions require service-side verification.'),
            @('NEXT STEP', 'Complete governance, lineage, approvals, and durable operations before production claims.')
        )
    }
)

$application = $null
$presentation = $null
try {
    $application = New-Object -ComObject PowerPoint.Application
    $application.Visible = -1
    $presentation = $application.Presentations.Add()
    $presentation.PageSetup.SlideSize = 16

    $cover = $presentation.Slides.Add(1, 12)
    $cover.Background.Fill.Solid()
    $cover.Background.Fill.ForeColor.RGB = Color 11 18 32
    AddRect $cover 0 0 0.16 7.5 (Color 34 211 238) | Out-Null
    AddText $cover 'DATASENTINEL AI' 0.8 0.6 5.2 0.35 14 (Color 34 211 238) $true | Out-Null
    AddText $cover "Reliable data in.`nSafer pipelines out." 0.8 1.65 8.0 1.75 36 (Color 248 250 252) $true | Out-Null
    AddText $cover 'Deterministic data-quality guardrails with an explainable, fail-closed protection gate.' 0.82 3.65 7.3 0.85 20 (Color 203 213 225) | Out-Null
    AddText $cover 'LOCAL DEMO  /  PHASE 4' 0.84 6.35 4.0 0.35 12 (Color 34 211 238) $true | Out-Null

    AddRect $cover 9.2 1.55 3.3 4.6 (Color 17 29 48) (Color 37 53 73) | Out-Null
    AddText $cover 'DETECTION' 9.55 2.05 2.6 0.35 16 (Color 248 250 252) $true | Out-Null
    AddText $cover 'v' 10.55 2.48 0.5 0.5 22 (Color 34 211 238) $true | Out-Null
    AddText $cover 'PROTECTION GATE' 9.55 3.03 2.8 0.4 15 (Color 248 250 252) $true | Out-Null
    AddText $cover 'ALLOW  /  HOLD  /  BLOCK' 9.55 3.48 2.85 0.3 11 (Color 148 163 184) | Out-Null
    AddText $cover 'v' 10.55 3.9 0.5 0.5 22 (Color 34 211 238) $true | Out-Null
    AddText $cover 'DOWNSTREAM' 9.55 4.45 2.8 0.35 15 (Color 248 250 252) $true | Out-Null
    AddText $cover 'Only exact ALLOW proceeds' 9.55 4.91 2.8 0.6 12 (Color 203 213 225) | Out-Null
    AddText $cover '01  /  08' 11.0 7.12 1.8 0.2 9 (Color 100 116 139) | Out-Null

    $page = 1
    foreach ($spec in $slides) {
        $page++
        $slide = AddBase $presentation $page $spec.Kicker $spec.Title $spec.Subtitle
        $count = $spec.Cards.Count
        $gap = 0.2
        $cardWidth = (12.05 - (($count - 1) * $gap)) / $count
        for ($i = 0; $i -lt $count; $i++) {
            $x = 0.58 + ($i * ($cardWidth + $gap))
            $accent = if ($i -eq 1) {
                Color 251 191 36
            } elseif ($i -eq 2) {
                Color 248 113 113
            } else {
                Color 34 211 238
            }
            AddCard $slide $spec.Cards[$i][0] $spec.Cards[$i][1] $x 2.85 $cardWidth 2.55 $accent
        }
        AddText $slide 'Decision authority: deterministic Python gate' 0.62 6.12 8.5 0.35 12 (Color 148 163 184) | Out-Null
    }

    $outputPath = Join-Path (Get-Location) 'docs\DataSentinelAI_Demo.pptx'
    $presentation.SaveAs($outputPath, 24)
    Write-Output "Created $outputPath ($($presentation.Slides.Count) slides)"
} finally {
    if ($null -ne $presentation) {
        try { $presentation.Close() } catch {}
    }
    if ($null -ne $application) {
        $application.Quit()
    }
    if ($null -ne $presentation) {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) | Out-Null
    }
    if ($null -ne $application) {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($application) | Out-Null
    }
}

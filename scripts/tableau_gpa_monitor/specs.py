"""Cumulative GPA Monitor build specs.

Extracted from build/20-goalstrip-full.twbx. Every field reference is a
CAPTION, never an internal id, so these re-apply to any baseline.
Regenerate with extract_specs.py.
"""

SPEC = {
    "datasource": {
        "name": "federated.0n798br073i5kb170j6l90uiv50a",
        "caption": "rpt_tableau__gpa_goal_progress (kipptaf_tableau)",
    },
    "parameters": [
        {
            "caption": "Grade view",
            "datatype": "integer",
            "type": "quantitative",
            "value": "11",
            "alias": "Grade 11",
            "members": [
                {"value": "9", "alias": "Grade 9"},
                {"value": "10", "alias": "Grade 10"},
                {"value": "11", "alias": "Grade 11"},
                {"value": "12", "alias": "Grade 12"},
            ],
        },
        {
            "caption": "GPA basis",
            "datatype": "string",
            "type": "nominal",
            "value": '"Projected EOY"',
            "alias": None,
            "members": [
                {"value": '"Projected EOY"', "alias": None},
                {"value": '"On the books today"', "alias": None},
            ],
        },
        {
            "caption": "Trend measure",
            "datatype": "string",
            "type": "nominal",
            "value": '"\\% at 3.0+"',
            "alias": None,
            "members": [
                {"value": '"\\% at 3.0+"', "alias": None},
                {"value": '"\\% at 3.5+"', "alias": None},
            ],
        },
        {
            "caption": "Special Populations",
            "datatype": "string",
            "type": "nominal",
            "value": '"IEP"',
            "alias": None,
            "members": [
                {"value": '"IEP"', "alias": None},
                {"value": '"MLL"', "alias": None},
                {"value": '"504"', "alias": None},
                {"value": '"G&T"', "alias": None},
            ],
        },
        {
            "caption": "p_Academic_Year",
            "datatype": "integer",
            "type": "quantitative",
            "value": "2026",
            "alias": "2026-27",
            "members": [
                {"value": "2025", "alias": "2025-26"},
                {"value": "2026", "alias": "2026-27"},
            ],
        },
        {
            "caption": "p_Region",
            "datatype": "string",
            "type": "nominal",
            "value": '"All"',
            "alias": None,
            "members": [
                {"value": '"All"', "alias": None},
                {"value": '"Newark"', "alias": None},
                {"value": '"Camden"', "alias": None},
            ],
        },
        {
            "caption": "p_Marking_Period",
            "datatype": "string",
            "type": "nominal",
            "value": '"Y1"',
            "alias": None,
            "members": [
                {"value": '"Q1"', "alias": None},
                {"value": '"Q2"', "alias": None},
                {"value": '"Q3"', "alias": None},
                {"value": '"Q4"', "alias": None},
                {"value": '"Y1"', "alias": None},
            ],
        },
        {
            "caption": "p_Subgroup",
            "datatype": "string",
            "type": "nominal",
            "value": '"IEP"',
            "alias": None,
            "members": [
                {"value": '"IEP"', "alias": None},
                {"value": '"MLL"', "alias": None},
                {"value": '"Gifted"', "alias": None},
                {"value": '"504"', "alias": None},
            ],
        },
        {
            "caption": "p_Custom_Cutoff",
            "datatype": "real",
            "type": "quantitative",
            "value": "0.",
            "alias": None,
            "members": [],
        },
        {
            "caption": "p_Include_Failing",
            "datatype": "boolean",
            "type": "nominal",
            "value": "true",
            "alias": None,
            "members": [
                {"value": "true", "alias": None},
                {"value": "false", "alias": None},
            ],
        },
        {
            "caption": "p_Include_Near_3",
            "datatype": "boolean",
            "type": "nominal",
            "value": "true",
            "alias": None,
            "members": [
                {"value": "true", "alias": None},
                {"value": "false", "alias": None},
            ],
        },
        {
            "caption": "p_Include_Near_2",
            "datatype": "boolean",
            "type": "nominal",
            "value": "false",
            "alias": None,
            "members": [
                {"value": "true", "alias": None},
                {"value": "false", "alias": None},
            ],
        },
    ],
    "calculated_fields": [
        {
            "caption": "Grade filter",
            "datatype": "boolean",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": "[Grade Level] = [Grade view]",
        },
        {
            "caption": "% at 3.0+ (shown)",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "p0.0%",
            "formula": "IF [Measured (projected)] < 10 THEN NULL\n"
            "ELSE [At 3.0+ (projected)] / [Measured "
            "(projected)]\n"
            "END",
        },
        {
            "caption": "Cum GPA",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": "Avg",
            "default_format": "n2",
            "formula": 'IF [GPA basis] = "Projected EOY"\n'
            "THEN [Cumulative Y1 Gpa Unweighted]\n"
            "ELSE [Cumulative Y1 Gpa Unweighted As Of Today]\n"
            "END",
        },
        {
            "caption": "Trend value",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "p0.0%",
            "formula": 'IF [Trend measure] = "% at 3.5+"\n'
            "THEN [At 3.5+ (projected)] / [Measured "
            "(projected)]\n"
            "ELSE [At 3.0+ (projected)] / [Measured "
            "(projected)]\n"
            "END",
        },
        {
            "caption": "Title",
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": '"Title"',
        },
        {
            "caption": "Measured",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF NOT ISNULL([Cum GPA]) THEN [Student Number] END)",
        },
        {
            "caption": "Reachable (projected)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "n0",
            "formula": "COUNTD(\n"
            "  IF [Cumulative Y1 Gpa Unweighted] < 3.0 AND [Is "
            "Cumulative 3 0 Attainable]\n"
            "  THEN [Student Number]\n"
            "  END\n"
            ")",
        },
        {
            "caption": "At 3.5+",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF [Cum GPA] >= 3.5 THEN [Student Number] END)",
        },
        {
            "caption": "Still reachable",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(\n"
            "  IF [Cum GPA] < 3.0 AND [Is Cumulative 3 0 "
            "Attainable]\n"
            "  THEN [Student Number]\n"
            "  END\n"
            ")",
        },
        {
            "caption": "On cusp (shown)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "IF [Measured (projected)] < 10 THEN NULL ELSE [On cusp] END",
        },
        {
            "caption": "Gap to goal (pts)",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": '*+0.0"PP";-0.0"PP";0.0"PP"',
            "formula": "([At 3.0+ (projected)] / [Measured (projected)]\n"
            ' - AVG(IF [p_Region] = "All"\n'
            "       THEN [Gpa Goal Proportion Org]\n"
            "       ELSE [Gpa Goal Proportion Region]\n"
            "       END)) * 100",
        },
        {
            "caption": "MLL status",
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": 'IF [Lep Status] THEN "Multilingual learner" ELSE '
            '"Not multilingual" END',
        },
        {
            "caption": "% at 3.5+",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "p0.0%",
            "formula": "[At 3.5+] / [Measured]",
        },
        {
            "caption": "Measured (projected)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF NOT ISNULL([Cumulative Y1 Gpa "
            "Unweighted]) THEN [Student Number] END)",
        },
        {
            "caption": "At 3.5+ (projected)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF [Cumulative Y1 Gpa Unweighted] >= 3.5 "
            "THEN [Student Number] END)",
        },
        {
            "caption": "On cusp",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF [Is On Cusp 3 0] THEN [Student Number] END)",
        },
        {
            "caption": "Students still needed",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "n0",
            "formula": "IF [At 3.0+ (projected)] / [Measured (projected)]\n"
            '   >= AVG(IF [p_Region] = "All"\n'
            "          THEN [Gpa Goal Proportion Org]\n"
            "          ELSE [Gpa Goal Proportion Region]\n"
            "          END)\n"
            "THEN 0\n"
            'ELSE ROUND(AVG(IF [p_Region] = "All"\n'
            "               THEN [Gpa Goal Proportion Org]\n"
            "               ELSE [Gpa Goal Proportion Region]\n"
            "               END) * [Measured (projected)])\n"
            "     - [At 3.0+ (projected)]\n"
            "END",
        },
        {
            "caption": "At 3.0+",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF [Cum GPA] >= 3.0 THEN [Student Number] END)",
        },
        {
            "caption": "Avg GPA (shown)",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "n2",
            "formula": "IF [Measured (projected)] < 10 THEN NULL\n"
            "ELSE AVG([Cumulative Y1 Gpa Unweighted])\n"
            "END",
        },
        {
            "caption": "Small group note",
            "datatype": "string",
            "role": "measure",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": 'IF [Measured (projected)] < 10 THEN "n<10 — '
            'hidden" ELSE "" END',
        },
        {
            "caption": "Gender label",
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": "CASE [Gender]\n"
            '  WHEN "F" THEN "Female"\n'
            '  WHEN "M" THEN "Male"\n'
            '  WHEN "X" THEN "Non-binary / X"\n'
            '  ELSE "Not reported"\n'
            "END",
        },
        {
            "caption": "Region filter",
            "datatype": "boolean",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": '[p_Region] = "All" OR [Region] = [p_Region]',
        },
        {
            "caption": "Ethnicity label",
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": "CASE [Ethnicity]\n"
            '  WHEN "A" THEN "Asian"\n'
            '  WHEN "B" THEN "Black"\n'
            '  WHEN "H" THEN "Hispanic / Latino"\n'
            '  WHEN "I" THEN "American Indian / Alaska Native"\n'
            '  WHEN "P" THEN "Native Hawaiian / Pacific '
            'Islander"\n'
            '  WHEN "T" THEN "Two or more races"\n'
            '  WHEN "W" THEN "White"\n'
            '  ELSE "Not reported"\n'
            "END",
        },
        {
            "caption": "Gap to 3.0",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": "Avg",
            "default_format": None,
            "formula": "3.00 - [Cum GPA]",
        },
        {
            "caption": "Below 3.0 (projected)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "n0",
            "formula": "COUNTD(IF [Cumulative Y1 Gpa Unweighted] < 3.0 "
            "THEN [Student Number] END)",
        },
        {
            "caption": "Goal status",
            "datatype": "string",
            "role": "measure",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": "IF ISNULL([At 3.0+ (projected)] / [Measured "
            '(projected)]) THEN "Not yet measured"\n'
            "ELSEIF [At 3.0+ (projected)] / [Measured "
            "(projected)]\n"
            '       >= AVG(IF [p_Region] = "All"\n'
            "              THEN [Gpa Goal Proportion Org]\n"
            "              ELSE [Gpa Goal Proportion Region]\n"
            "              END)\n"
            '     THEN "At or above goal"\n'
            'ELSE "Below goal"\n'
            "END",
        },
        {
            "caption": "Reachable?",
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": 'IF [Is Cumulative 3 0 Attainable] THEN "Yes" ELSE "No" END',
        },
        {
            "caption": "Measured (on the books)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(\n"
            "  IF NOT ISNULL([Cumulative Y1 Gpa Unweighted As "
            "Of Today])\n"
            "  THEN [Student Number]\n"
            "  END\n"
            ")",
        },
        {
            "caption": "Year filter",
            "datatype": "boolean",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": "[Academic Year] = [p_Academic_Year]",
        },
        {
            "caption": "GPA band",
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": None,
            "default_format": None,
            "formula": 'IF [GPA basis] = "Projected EOY"\n'
            "THEN [Gpa Band Label]\n"
            "ELSE [Gpa Band As Of Today Label]\n"
            "END",
        },
        {
            "caption": "% at 3.0+",
            "datatype": "real",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": "p0.0%",
            "formula": "[At 3.0+] / [Measured]",
        },
        {
            "caption": "At 3.0+ (projected)",
            "datatype": "integer",
            "role": "measure",
            "type": "quantitative",
            "aggregation": None,
            "default_format": None,
            "formula": "COUNTD(IF [Cumulative Y1 Gpa Unweighted] >= 3.0 "
            "THEN [Student Number] END)",
        },
    ],
    "worksheets": [
        {
            "name": "GPA - BAN % 3.0+",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "% at 3.0+", "deriv": "User"}],
                "tooltip": [
                    {"field": "At 3.0+", "deriv": "User"},
                    {"field": "Measured", "deriv": "User"},
                ],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [{"field": "% at 3.0+", "format": "*0.0%"}],
            "label": [
                {
                    "text": "At 3.0+ cumulative",
                    "size": "13",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_9335003396903351453:qk]>",
                    "size": "30",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - BAN % 3.5+",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "% at 3.5+", "deriv": "User"}],
                "tooltip": [
                    {"field": "On cusp", "deriv": "User"},
                    {"field": "Still reachable", "deriv": "User"},
                ],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [{"field": "% at 3.5+", "format": "*0.0%"}],
            "label": [
                {
                    "text": "At 3.5+ cumulative",
                    "size": "13",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_4645249709926099321:qk]>",
                    "size": "30",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - BAN Avg cum GPA",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "Cum GPA", "deriv": "Avg"}],
                "tooltip": [{"field": "Measured", "deriv": "User"}],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [{"field": "Cum GPA", "format": "*0.00"}],
            "label": [
                {
                    "text": "Average cumulative GPA",
                    "size": "13",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[avg:Calculation_0141679102236570168:qk]>",
                    "size": "30",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - BAN Below 3.0",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "Below 3.0 (projected)", "deriv": "User"}],
                "tooltip": [{"field": "Measured (projected)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [{"field": "Below 3.0 (projected)", "format": "#,##0"}],
            "label": [
                {
                    "text": "Students below 3.0 — always projected",
                    "size": "13",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_6742351851630427295:qk]>",
                    "size": "30",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - BAN Can reach",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "Reachable (projected)", "deriv": "User"}],
                "tooltip": [{"field": "Below 3.0 (projected)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [{"field": "Reachable (projected)", "format": "#,##0"}],
            "label": [
                {
                    "text": "Of those, can still get there — always projected",
                    "size": "13",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_2020978725030741172:qk]>",
                    "size": "30",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - BAN Gap to goal",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "color": [{"field": "Goal status", "deriv": "User"}],
                "text": [{"field": "Gap to goal (pts)", "deriv": "User"}],
                "tooltip": [
                    {"field": "% at 3.0+", "deriv": "User"},
                    {"field": "Gpa Goal Proportion Org", "deriv": "Avg"},
                ],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [
                {"field": "Gap to goal (pts)", "format": '*+0.0"PP";-0.0"PP";0.0"PP"'}
            ],
            "label": [
                {
                    "text": "Gap to goal, pts — always projected",
                    "size": "10",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_3466859908724272046:qk]>",
                    "size": "20",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - BAN Students needed",
            "mark": "Text",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "Students still needed", "deriv": "User"}],
                "tooltip": [
                    {"field": "At 3.0+", "deriv": "User"},
                    {"field": "Measured", "deriv": "User"},
                    {"field": "Gpa Goal Proportion Org", "deriv": "Avg"},
                ],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [{"field": "Students still needed", "format": "#,##0"}],
            "label": [
                {
                    "text": "Students still needed — always projected",
                    "size": "10",
                    "bold": None,
                    "color": None,
                },
                {"text": "Æ\n", "size": None, "bold": None, "color": None},
                {
                    "text": "<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_5262281088199017638:qk]>",
                    "size": "20",
                    "bold": None,
                    "color": "#001e62",
                },
            ],
            "align": "center",
            "stroke": False,
        },
        {
            "name": "GPA - Cusp roster",
            "mark": "Text",
            "shelves": {
                "rows": [
                    {"field": "Student Name", "deriv": "None", "pct_of_total": False},
                    {"field": "School", "deriv": "None", "pct_of_total": False},
                    {"field": "Reachable?", "deriv": "None", "pct_of_total": False},
                ],
                "cols": [
                    {"field": ":Measure Names", "deriv": None, "pct_of_total": False}
                ],
                "text": [{"field": ":Measure Values", "deriv": None}],
                "lod": [{"field": "Student Number", "deriv": "None"}],
            },
            "filters": [
                {
                    "field": "[:Measure Names]",
                    "kind": "members",
                    "values": [
                        '"[federated.0n798br073i5kb170j6l90uiv50a].[avg:Calculation_0141679102236570168:qk]"',
                        '"[federated.0n798br073i5kb170j6l90uiv50a].[avg:Calculation_6622407987147527517:qk]"',
                        '"[federated.0n798br073i5kb170j6l90uiv50a].[min:gpa_needed_for_cumulative_3_0:qk]"',
                    ],
                },
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
                {"field": "Is On Cusp 3 0", "kind": "member", "value": "true"},
            ],
            "formats": [],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Dist by grade",
            "mark": "Bar",
            "shelves": {
                "rows": [{"field": "Measured", "deriv": "User", "pct_of_total": True}],
                "cols": [
                    {"field": "Grade Level", "deriv": "None", "pct_of_total": False}
                ],
                "color": [{"field": "GPA band", "deriv": "None"}],
                "text": [{"field": "Measured", "deriv": "User"}],
                "tooltip": [{"field": "Measured", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
                {"field": "GPA band", "kind": "exclude_null"},
            ],
            "formats": [],
            "label": None,
            "align": None,
            "stroke": True,
        },
        {
            "name": "GPA - Dist on the books",
            "mark": "Bar",
            "shelves": {
                "rows": [],
                "cols": [
                    {
                        "field": "Measured (on the books)",
                        "deriv": "User",
                        "pct_of_total": True,
                    }
                ],
                "color": [{"field": "Gpa Band As Of Today Label", "deriv": "None"}],
                "text": [{"field": "Measured (on the books)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
                {"field": "Gpa Band As Of Today Label", "kind": "exclude_null"},
            ],
            "formats": [],
            "label": None,
            "align": None,
            "stroke": True,
        },
        {
            "name": "GPA - Dist projected",
            "mark": "Bar",
            "shelves": {
                "rows": [],
                "cols": [
                    {
                        "field": "Measured (projected)",
                        "deriv": "User",
                        "pct_of_total": True,
                    }
                ],
                "color": [{"field": "Gpa Band Label", "deriv": "None"}],
                "text": [{"field": "Measured (projected)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Grade filter", "kind": "member", "value": "true"},
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
                {"field": "Gpa Band Label", "kind": "exclude_null"},
            ],
            "formats": [],
            "label": None,
            "align": None,
            "stroke": True,
        },
        {
            "name": "GPA - Equity Gender",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {"field": "Gender label", "deriv": "None", "pct_of_total": False}
                ],
                "cols": [
                    {
                        "field": "% at 3.0+ (shown)",
                        "deriv": "User",
                        "pct_of_total": False,
                    }
                ],
                "text": [
                    {"field": "Avg GPA (shown)", "deriv": "User"},
                    {"field": "Small group note", "deriv": "User"},
                ],
                "tooltip": [{"field": "On cusp (shown)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [
                {"field": "% at 3.0+ (shown)", "format": "*0.0%"},
                {"field": "Avg GPA (shown)", "format": "*0.00"},
            ],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Equity IEP",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {"field": "Iep Status", "deriv": "None", "pct_of_total": False}
                ],
                "cols": [
                    {
                        "field": "% at 3.0+ (shown)",
                        "deriv": "User",
                        "pct_of_total": False,
                    }
                ],
                "text": [
                    {"field": "Avg GPA (shown)", "deriv": "User"},
                    {"field": "Small group note", "deriv": "User"},
                ],
                "tooltip": [{"field": "On cusp (shown)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [
                {"field": "% at 3.0+ (shown)", "format": "*0.0%"},
                {"field": "Avg GPA (shown)", "format": "*0.00"},
            ],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Equity MLL",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {"field": "MLL status", "deriv": "None", "pct_of_total": False}
                ],
                "cols": [
                    {
                        "field": "% at 3.0+ (shown)",
                        "deriv": "User",
                        "pct_of_total": False,
                    }
                ],
                "text": [
                    {"field": "Avg GPA (shown)", "deriv": "User"},
                    {"field": "Small group note", "deriv": "User"},
                ],
                "tooltip": [{"field": "On cusp (shown)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [
                {"field": "% at 3.0+ (shown)", "format": "*0.0%"},
                {"field": "Avg GPA (shown)", "format": "*0.00"},
            ],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Equity Race",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {"field": "Ethnicity label", "deriv": "None", "pct_of_total": False}
                ],
                "cols": [
                    {
                        "field": "% at 3.0+ (shown)",
                        "deriv": "User",
                        "pct_of_total": False,
                    }
                ],
                "text": [
                    {"field": "Avg GPA (shown)", "deriv": "User"},
                    {"field": "Small group note", "deriv": "User"},
                ],
                "tooltip": [{"field": "On cusp (shown)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {"field": "Year filter", "kind": "member", "value": "true"},
            ],
            "formats": [
                {"field": "% at 3.0+ (shown)", "format": "*0.0%"},
                {"field": "Avg GPA (shown)", "format": "*0.00"},
            ],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Goal by grade",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {"field": "% at 3.0+", "deriv": "User", "pct_of_total": False}
                ],
                "cols": [
                    {"field": "Grade Level", "deriv": "None", "pct_of_total": False}
                ],
                "color": [{"field": "Goal status", "deriv": "User"}],
                "text": [{"field": "% at 3.0+", "deriv": "User"}],
                "tooltip": [
                    {"field": "Gpa Goal Proportion Org", "deriv": "Avg"},
                    {"field": "Gap to goal (pts)", "deriv": "User"},
                    {"field": "Students still needed", "deriv": "User"},
                    {"field": "Measured", "deriv": "User"},
                ],
                "lod": [{"field": "Gpa Goal Proportion Org", "deriv": "Avg"}],
            },
            "filters": [{"field": "Year filter", "kind": "member", "value": "true"}],
            "formats": [{"field": "% at 3.0+", "format": "*0.0%"}],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Goal by school",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {"field": "School", "deriv": "None", "pct_of_total": False},
                    {"field": "Grade Level", "deriv": "None", "pct_of_total": False},
                ],
                "cols": [
                    {"field": "% at 3.0+", "deriv": "User", "pct_of_total": False}
                ],
                "color": [{"field": "Goal status", "deriv": "User"}],
                "text": [{"field": "Gap to goal (pts)", "deriv": "User"}],
                "tooltip": [
                    {"field": "% at 3.0+", "deriv": "User"},
                    {"field": "Gpa Goal Proportion School", "deriv": "Avg"},
                    {"field": "Students still needed", "deriv": "User"},
                ],
                "lod": [{"field": "Gpa Goal Proportion School", "deriv": "Avg"}],
            },
            "filters": [{"field": "Year filter", "kind": "member", "value": "true"}],
            "formats": [
                {"field": "% at 3.0+", "format": "*0.0%"},
                {"field": "Gap to goal (pts)", "format": '*+0.0"PP";-0.0"PP";0.0"PP"'},
            ],
            "label": None,
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Splay over time",
            "mark": "Bar",
            "shelves": {
                "rows": [
                    {
                        "field": "Measured (projected)",
                        "deriv": "User",
                        "pct_of_total": True,
                    }
                ],
                "cols": [
                    {"field": "Academic Year", "deriv": "None", "pct_of_total": False}
                ],
                "color": [{"field": "Gpa Band Label", "deriv": "None"}],
                "text": [{"field": "Measured (projected)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {
                    "field": "Academic Year",
                    "kind": "members",
                    "values": ["2021", "2022", "2023", "2024", "2025"],
                },
                {"field": "Gpa Band Label", "kind": "exclude_null"},
                {"field": "Grade Level", "kind": "members", "values": ["11"]},
                {"field": "Is Projected", "kind": "member", "value": "false"},
            ],
            "formats": [],
            "label": None,
            "align": None,
            "stroke": True,
        },
        {
            "name": "GPA - Title",
            "mark": "Automatic",
            "shelves": {
                "rows": [],
                "cols": [],
                "text": [{"field": "Title", "deriv": "None"}],
            },
            "filters": [],
            "formats": [],
            "label": [
                {"text": "Cumulative GPA", "size": "16", "bold": "true", "color": None},
                {"text": " | Monitor", "size": "16", "bold": None, "color": None},
            ],
            "align": None,
            "stroke": False,
        },
        {
            "name": "GPA - Trend by grade",
            "mark": "Line",
            "shelves": {
                "rows": [
                    {"field": "Trend value", "deriv": "User", "pct_of_total": False}
                ],
                "cols": [
                    {"field": "Academic Year", "deriv": "None", "pct_of_total": False}
                ],
                "color": [{"field": "Grade Level", "deriv": "None"}],
                "tooltip": [{"field": "Measured (projected)", "deriv": "User"}],
            },
            "filters": [
                {"field": "Region filter", "kind": "member", "value": "true"},
                {
                    "field": "Academic Year",
                    "kind": "members",
                    "values": ["2021", "2022", "2023", "2024", "2025"],
                },
                {"field": "Is Projected", "kind": "member", "value": "false"},
            ],
            "formats": [{"field": "Trend value", "format": "*0.0%"}],
            "label": None,
            "align": None,
            "stroke": False,
        },
    ],
    "dashboard": {
        "name": "Cumulative GPA Monitor",
        "size": {
            "minwidth": "1366",
            "maxwidth": "1366",
            "minheight": "900",
            "maxheight": "900",
            "sizing-mode": "fixed",
        },
        "zones": [
            {
                "friendly": None,
                "type": "layout-basic",
                "param": None,
                "sheet": None,
                "fixed_size": None,
                "w": "100000",
                "h": "100000",
                "x": "0",
                "y": "0",
                "background": "#001e62",
                "children": [
                    {
                        "friendly": None,
                        "type": "layout-flow",
                        "param": "vert",
                        "sheet": None,
                        "fixed_size": None,
                        "w": "100000",
                        "h": "100000",
                        "x": "0",
                        "y": "0",
                        "background": "#001e62",
                        "children": [
                            {
                                "friendly": "Title",
                                "type": "layout-flow",
                                "param": "horz",
                                "sheet": None,
                                "fixed_size": "60",
                                "w": "100000",
                                "h": "6667",
                                "x": "0",
                                "y": "0",
                                "background": "#001e62",
                                "children": [
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - Title",
                                        "fixed_size": None,
                                        "w": "100000",
                                        "h": "6667",
                                        "x": "0",
                                        "y": "0",
                                    }
                                ],
                            },
                            {
                                "friendly": "Controls",
                                "type": "layout-flow",
                                "param": "horz",
                                "sheet": None,
                                "fixed_size": "60",
                                "w": "100000",
                                "h": "7556",
                                "x": "0",
                                "y": "6667",
                                "children": [
                                    {
                                        "friendly": None,
                                        "type": "paramctrl",
                                        "param": "[Parameters].[Parameter 2]",
                                        "sheet": None,
                                        "fixed_size": None,
                                        "w": "24890",
                                        "h": "6667",
                                        "x": "293",
                                        "y": "7111",
                                    },
                                    {
                                        "friendly": None,
                                        "type": "paramctrl",
                                        "param": "[Parameters].[Parameter 3]",
                                        "sheet": None,
                                        "fixed_size": None,
                                        "w": "24890",
                                        "h": "6667",
                                        "x": "25183",
                                        "y": "7111",
                                    },
                                    {
                                        "friendly": None,
                                        "type": "paramctrl",
                                        "param": "[Parameters].[Parameter 10]",
                                        "sheet": None,
                                        "fixed_size": None,
                                        "w": "24817",
                                        "h": "6667",
                                        "x": "50073",
                                        "y": "7111",
                                    },
                                    {
                                        "friendly": None,
                                        "type": "paramctrl",
                                        "param": "[Parameters].[Parameter 11]",
                                        "sheet": None,
                                        "fixed_size": None,
                                        "w": "24817",
                                        "h": "6667",
                                        "x": "74890",
                                        "y": "7111",
                                    },
                                ],
                            },
                            {
                                "friendly": "Headline",
                                "type": "layout-flow",
                                "param": "horz",
                                "sheet": None,
                                "fixed_size": "130",
                                "w": "100000",
                                "h": "15333",
                                "x": "0",
                                "y": "14223",
                                "children": [
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN % 3.0+",
                                        "fixed_size": None,
                                        "w": "19912",
                                        "h": "14444",
                                        "x": "293",
                                        "y": "14667",
                                    },
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN Below 3.0",
                                        "fixed_size": None,
                                        "w": "19912",
                                        "h": "14444",
                                        "x": "20205",
                                        "y": "14667",
                                    },
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN Can reach",
                                        "fixed_size": None,
                                        "w": "19912",
                                        "h": "14444",
                                        "x": "40117",
                                        "y": "14667",
                                    },
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN Avg cum GPA",
                                        "fixed_size": None,
                                        "w": "19839",
                                        "h": "14444",
                                        "x": "60029",
                                        "y": "14667",
                                    },
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN % 3.5+",
                                        "fixed_size": None,
                                        "w": "19839",
                                        "h": "14444",
                                        "x": "79868",
                                        "y": "14667",
                                    },
                                ],
                            },
                            {
                                "friendly": "Goal strip",
                                "type": "layout-flow",
                                "param": "horz",
                                "sheet": None,
                                "fixed_size": "70",
                                "w": "100000",
                                "h": "8667",
                                "x": "0",
                                "y": "29556",
                                "children": [
                                    {
                                        "friendly": None,
                                        "type": "text",
                                        "param": None,
                                        "sheet": None,
                                        "fixed_size": "200",
                                        "w": "15227",
                                        "h": "7779",
                                        "x": "293",
                                        "y": "30000",
                                    },
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN Gap to goal",
                                        "fixed_size": None,
                                        "w": "42093",
                                        "h": "7779",
                                        "x": "15520",
                                        "y": "30000",
                                    },
                                    {
                                        "friendly": None,
                                        "type": None,
                                        "param": None,
                                        "sheet": "GPA - BAN Students needed",
                                        "fixed_size": None,
                                        "w": "42093",
                                        "h": "7779",
                                        "x": "57613",
                                        "y": "30000",
                                    },
                                ],
                            },
                            {
                                "friendly": "Body",
                                "type": "layout-flow",
                                "param": "horz",
                                "sheet": None,
                                "fixed_size": None,
                                "w": "100000",
                                "h": "61777",
                                "x": "0",
                                "y": "38223",
                                "children": [
                                    {
                                        "friendly": "Body left",
                                        "type": "layout-flow",
                                        "param": "vert",
                                        "sheet": None,
                                        "fixed_size": "800",
                                        "w": "59151",
                                        "h": "60889",
                                        "x": "293",
                                        "y": "38667",
                                        "children": [
                                            {
                                                "friendly": None,
                                                "type": None,
                                                "param": None,
                                                "sheet": "GPA - Dist on the books",
                                                "fixed_size": "80",
                                                "w": "58565",
                                                "h": "9778",
                                                "x": "586",
                                                "y": "39111",
                                            },
                                            {
                                                "friendly": None,
                                                "type": None,
                                                "param": None,
                                                "sheet": "GPA - Dist projected",
                                                "fixed_size": "80",
                                                "w": "58565",
                                                "h": "9778",
                                                "x": "586",
                                                "y": "48889",
                                            },
                                            {
                                                "friendly": None,
                                                "type": "color",
                                                "param": "[federated.0n798br073i5kb170j6l90uiv50a].[none:gpa_band_label:nk]",
                                                "sheet": "GPA - Dist projected",
                                                "fixed_size": "30",
                                                "w": "58565",
                                                "h": "4222",
                                                "x": "586",
                                                "y": "58667",
                                            },
                                            {
                                                "friendly": None,
                                                "type": None,
                                                "param": None,
                                                "sheet": "GPA - Dist by grade",
                                                "fixed_size": None,
                                                "w": "58565",
                                                "h": "36223",
                                                "x": "586",
                                                "y": "62889",
                                            },
                                        ],
                                    },
                                    {
                                        "friendly": "Body right",
                                        "type": "layout-flow",
                                        "param": "vert",
                                        "sheet": None,
                                        "fixed_size": None,
                                        "w": "40262",
                                        "h": "60889",
                                        "x": "59444",
                                        "y": "38667",
                                        "children": [
                                            {
                                                "friendly": None,
                                                "type": None,
                                                "param": None,
                                                "sheet": "GPA - Goal by grade",
                                                "fixed_size": None,
                                                "w": "39676",
                                                "h": "15668",
                                                "x": "59737",
                                                "y": "39111",
                                            },
                                            {
                                                "friendly": None,
                                                "type": None,
                                                "param": None,
                                                "sheet": "GPA - Goal by school",
                                                "fixed_size": None,
                                                "w": "39676",
                                                "h": "44333",
                                                "x": "59737",
                                                "y": "54779",
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    },
    "colours": [
        {
            "field": "GPA band",
            "derivation": "None",
            "map": [
                {"value": '"3.5+"', "hex": "#001e62"},
                {"value": '"3.0-3.49"', "hex": "#2f5fc4"},
                {"value": '"2.5-2.99"', "hex": "#b6c0cf"},
                {"value": '"2.0-2.49"', "hex": "#f9a21a"},
                {"value": '"below 2.0"', "hex": "#d8342f"},
                {"value": "%null%", "hex": "#edc948"},
            ],
        },
        {
            "field": "Gpa Band Label",
            "derivation": "None",
            "map": [
                {"value": '"3.5+"', "hex": "#001e62"},
                {"value": '"3.0-3.49"', "hex": "#2f5fc4"},
                {"value": '"2.5-2.99"', "hex": "#b6c0cf"},
                {"value": '"2.0-2.49"', "hex": "#f9a21a"},
                {"value": '"below 2.0"', "hex": "#d8342f"},
                {"value": "%null%", "hex": "#edc948"},
            ],
        },
        {
            "field": "Gpa Band As Of Today Label",
            "derivation": "None",
            "map": [
                {"value": '"3.5+"', "hex": "#001e62"},
                {"value": '"3.0-3.49"', "hex": "#2f5fc4"},
                {"value": '"2.5-2.99"', "hex": "#b6c0cf"},
                {"value": '"2.0-2.49"', "hex": "#f9a21a"},
                {"value": '"below 2.0"', "hex": "#d8342f"},
                {"value": "%null%", "hex": "#edc948"},
            ],
        },
        {
            "field": "Goal status",
            "derivation": "User",
            "map": [
                {"value": '"At or above goal"', "hex": "#2f5fc4"},
                {"value": '"Below goal"', "hex": "#d8342f"},
                {"value": '"Not yet measured"', "hex": "#b6c0cf"},
                {"value": "%null%", "hex": "#edc948"},
            ],
        },
    ],
}

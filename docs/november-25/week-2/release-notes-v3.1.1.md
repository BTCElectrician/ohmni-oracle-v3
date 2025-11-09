# Ohmni Oracle v3.1.1 - Performance Baseline & Production Stable

**Release Date:** November 9, 2025  
**Type:** Baseline Release  
**Status:** Production Stable

## 📋 Overview

This release establishes a performance baseline before a major refactor. All metrics are based on a comprehensive test run conducted on November 8, 2025.

## 📈 Baseline Processing Statistics (2025-11-08)

Test involved **9 total operations** for main processing steps and **17 API requests**.

### ⏱️ Overall Average Durations

Total overall average duration for processing one file: **86.80 seconds**

| Processing Stage | Overall Average Duration (seconds) |
| :--- | :--- |
| **Total Processing** | **86.80** |
| AI Processing | 76.61 |
| API Request | 40.56 |
| Extraction (Total) | 7.17 |
| Extraction (PDF Read) | 7.17 |
| JSON Parsing | 1.09 |
| Queue Waiting | 0.00029 |
| Normalization | 0.00006 |

### 🐌 Slowest Operations

The two longest operations were in the **Mechanical** and **Electrical** drawing types.

| File Name | Drawing Type | Total Processing Duration (seconds) |
| :--- | :--- | :--- |
| **M6.01-MECHANICAL---SCHEDULES-Rev.3.pdf** | **Mechanical** | **160.55** |
| **E5.00-PANEL-SCHEDULES-Rev.3 copy.pdf** | **Electrical** | **123.79** |

### 🧠 AI Processing Averages by Drawing Type

The **Plumbing** and **Electrical** drawing types had the longest average AI Processing times.

| Drawing Type | AI Processing Average Duration (seconds) |
| :--- | :--- |
| **Plumbing** | **106.89** |
| **Electrical** | **106.22** |
| Mechanical | 87.97 |
| Architectural | 64.24 |
| Technology | 15.23 |
| Equipment | 8.52 |

### 🌐 API Statistics

The **API Request** component accounted for approximately **88.25%** of the total processing time.

- **Average API Request Time:** 40.56 seconds
- **Total API Requests:** 17
- **Average Tokens per Second:** 69.74
- **Most Used Model by Token Count:** `gpt-4.1-mini` (33,944 total completion tokens)

## 🎯 Purpose

This baseline establishes a revert point before major refactoring work. All features are stable and production-ready.

## 🔧 Configuration

- **Default Model:** gpt-4.1-mini
- **Large Doc Model:** gpt-4.1
- **Schedule Model:** gpt-4.1-mini
- **AI Cache:** Enabled
- **OCR:** Enabled (threshold-based)
- **Metadata Repair:** Enabled
- **JSON Repair:** Enabled

## 📦 What's Included

- AI search index integration (complete)
- Forced OCR on panel schedules
- Flexible circuit normalization with stable ordering
- Source document archiving (local/Azure Blob)
- Comprehensive room template system
- Performance metrics tracking

## ⚠️ Notes

- Performance may vary ±15-25% due to OpenAI API server load
- This is normal and expected behavior
- Baseline established for comparison against future optimizations

## 🔗 Related Documentation

- [AI Search Index Integration](../week-1/ai-search-index-integration-11-07-25.md)
- [Comprehensive Template Guide](../../templates/COMPREHENSIVE_TEMPLATE_GUIDE.md)
- [Performance Baseline (October 2025)](../../october/performance-baseline-benchmark-10-28-25.md)

---

**Developer:** Collin (BTCElectrician)  
**Commit:** bec5d73 (latest at time of release)


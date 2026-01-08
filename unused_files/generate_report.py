#!/usr/bin/env python3
"""
Generate human-readable reports from test analysis.
Usage: python generate_report.py [--format text|markdown]
"""
import json
import argparse
from pathlib import Path
from datetime import datetime


class ReportGenerator:
    """Generate human-readable reports from analysis data."""

    def __init__(self, analysis_file: str = None):
        """Load the most recent analysis if no file specified."""
        if analysis_file:
            self.data = self._load_analysis(analysis_file)
        else:
            # Find most recent analysis
            analysis_dir = Path('test_results/analysis')
            if analysis_dir.exists():
                files = sorted(analysis_dir.glob('*_analysis_*.json'))
                if files:
                    self.data = self._load_analysis(files[-1])
                else:
                    raise FileNotFoundError("No analysis files found")
            else:
                raise FileNotFoundError("Analysis directory not found")

    def _load_analysis(self, filepath):
        """Load analysis JSON file."""
        with open(filepath) as f:
            return json.load(f)

    def generate_text_report(self):
        """Generate plain text report."""
        insights = self.data['insights']
        queue = self.data['queue_analysis']
        execution = self.data['execution_analysis']
        utilization = self.data['utilization_analysis']
        metrics = self.data['metrics']

        report = []
        report.append("=" * 70)
        report.append(f"  PERFORMANCE TEST ANALYSIS REPORT")
        report.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)
        report.append("")

        # Executive Summary
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 40)
        report.append(f"Test Type:           {self.data.get('test_type', 'Performance').upper()}")
        report.append(f"Workflows Analyzed:  {metrics['job_count']}")
        report.append(f"Overall Status:      {self._get_overall_status()}")
        report.append("")

        # Key Metrics Table
        report.append("KEY METRICS")
        report.append("-" * 40)
        report.append(f"{'Metric':<25} {'Value':<20} {'Status':<15}")
        report.append("-" * 60)

        avg_total = insights['user_experience']['avg_wait_time']
        avg_queue = queue['metrics']['average']
        avg_exec = execution['metrics']['average']
        queue_impact = insights['summary']['queue_impact_pct']
        util = utilization['metrics']['average']

        report.append(f"{'Average Total Time':<25} {avg_total:<20} {self._status_indicator(avg_total, 'total_time'):<15}")
        report.append(f"{'Average Queue Time':<25} {f'{avg_queue:.1f} minutes':<20} {self._status_indicator(avg_queue, 'queue_time'):<15}")
        report.append(f"{'Average Execution Time':<25} {f'{avg_exec:.1f} minutes':<20} {self._status_indicator(avg_exec, 'exec_time'):<15}")
        report.append(f"{'Queue Impact':<25} {f'{queue_impact:.0f}% of total':<20} {self._status_indicator(queue_impact, 'queue_impact'):<15}")
        report.append(f"{'Runner Utilization':<25} {f'{util:.1f}%':<20} {self._status_indicator(util, 'utilization'):<15}")
        report.append("")

        # Queue Analysis
        report.append("QUEUE ANALYSIS")
        report.append("-" * 40)
        report.append(f"Health Status:       {queue['health']}")
        report.append(f"Pattern:             {queue['growth_pattern']}")
        report.append(f"Average Queue:       {queue['metrics']['average']:.1f} minutes")
        report.append(f"Maximum Queue:       {queue['metrics']['maximum']:.1f} minutes")
        report.append(f"Jobs Queued:         {queue['metrics']['jobs_queued']}/{metrics['job_count']} ({queue['metrics']['jobs_queued']/metrics['job_count']*100:.0f}%)")
        report.append("")
        report.append("Interpretation:")
        report.append(f"  {queue['interpretation']}")
        report.append("")

        # Execution Analysis
        report.append("EXECUTION TIME ANALYSIS")
        report.append("-" * 40)
        report.append(f"Consistency:         {execution['consistency']}")
        report.append(f"Average Execution:   {execution['metrics']['average']:.1f} minutes")
        report.append(f"Variation (CV):      {execution['metrics']['coefficient_variation']:.0f}%")
        report.append(f"Expected Range:      {execution['range_compliance']['expected_range']}")
        report.append(f"Within Range:        {execution['range_compliance']['within_range_pct']:.0f}%")
        report.append("")

        # User Experience
        report.append("USER EXPERIENCE")
        report.append("-" * 40)
        report.append(f"Rating:              {insights['user_experience']['rating']}")
        report.append(f"Description:         {insights['user_experience']['description']}")
        report.append(f"Average Wait:        {insights['user_experience']['avg_wait_time']}")
        report.append("")

        # Key Findings
        report.append("KEY FINDINGS")
        report.append("-" * 40)
        for finding in insights['key_findings']:
            # Clean up Unicode characters for plain text
            clean_finding = finding.replace('⚠️', '[!]').replace('🔍', '[>]')
            report.append(f"  • {clean_finding}")
        report.append("")

        # Recommendations
        report.append("RECOMMENDATIONS")
        report.append("-" * 40)
        all_recs = []

        # Combine recommendations from different analyses
        for rec in queue.get('recommendations', []):
            all_recs.append(('Queue', rec))
        for rec in execution.get('recommendations', []):
            all_recs.append(('Execution', rec))
        for rec in utilization.get('recommendations', []):
            all_recs.append(('Utilization', rec))

        # Also add action items
        for action in insights.get('action_items', []):
            clean_action = action.replace('🔴', '[HIGH]').replace('🟡', '[MED]').replace('✅', '[OK]')
            all_recs.append(('Action', clean_action))

        for category, rec in all_recs:
            report.append(f"  [{category}] {rec}")
        report.append("")

        # System Details
        report.append("SYSTEM DETAILS")
        report.append("-" * 40)
        capacity = insights['capacity']
        report.append(f"Current Runners:     {capacity['current_runners']}")
        report.append(f"Current Rate:        {capacity['current_rate']}")
        report.append(f"Sustainable Rate:    {capacity['sustainable_rate']}")
        report.append(f"System Health:       {insights['system_health']}")
        report.append("")

        report.append("=" * 70)
        report.append("END OF REPORT")
        report.append("")

        return "\n".join(report)

    def _get_overall_status(self):
        """Determine overall status from metrics."""
        queue_health = self.data['queue_analysis']['health']
        exec_consistency = self.data['execution_analysis']['consistency']

        if queue_health in ['POOR'] or exec_consistency in ['HIGH_VARIATION']:
            return "⚠️  ISSUES DETECTED"
        elif queue_health in ['EXCELLENT', 'GOOD']:
            return "✅ HEALTHY"
        else:
            return "⚠️  MODERATE ISSUES"

    def _status_indicator(self, value, metric_type):
        """Return status indicator for different metrics."""
        if metric_type == 'queue_time':
            value_num = float(str(value).split()[0]) if isinstance(value, str) else value
            if value_num < 0.5:
                return "✅ EXCELLENT"
            elif value_num < 2:
                return "✅ GOOD"
            elif value_num < 5:
                return "⚠️  MODERATE"
            else:
                return "❌ POOR"
        elif metric_type == 'total_time':
            value_num = float(str(value).split()[0]) if isinstance(value, str) else value
            if value_num < 5:
                return "✅ EXCELLENT"
            elif value_num < 10:
                return "⚠️  FAIR"
            else:
                return "❌ POOR"
        elif metric_type == 'queue_impact':
            if value < 10:
                return "✅ MINIMAL"
            elif value < 30:
                return "⚠️  MODERATE"
            else:
                return "❌ HIGH"
        elif metric_type == 'utilization':
            if 70 <= value <= 85:
                return "✅ OPTIMAL"
            elif value > 95:
                return "❌ OVERLOAD"
            elif value < 50:
                return "⚠️  LOW"
            else:
                return "✅ GOOD"
        return ""

    def generate_markdown_report(self):
        """Generate Markdown report."""
        # Similar to text but with Markdown formatting
        insights = self.data['insights']
        queue = self.data['queue_analysis']
        execution = self.data['execution_analysis']
        utilization = self.data['utilization_analysis']
        metrics = self.data['metrics']

        md = []
        md.append("# Performance Test Analysis Report")
        md.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append("")

        md.append("## Executive Summary")
        md.append(f"- **Test Type**: {self.data.get('test_type', 'Performance').upper()}")
        md.append(f"- **Workflows Analyzed**: {metrics['job_count']}")
        md.append(f"- **Overall Status**: {self._get_overall_status()}")
        md.append("")

        md.append("## Key Metrics")
        md.append("")
        md.append("| Metric | Value | Status |")
        md.append("|--------|-------|--------|")

        avg_total = insights['user_experience']['avg_wait_time']
        avg_queue = queue['metrics']['average']
        avg_exec = execution['metrics']['average']
        queue_impact = insights['summary']['queue_impact_pct']
        util = utilization['metrics']['average']

        md.append(f"| Average Total Time | {avg_total} | {self._status_indicator(avg_total, 'total_time')} |")
        md.append(f"| Average Queue Time | {avg_queue:.1f} minutes | {self._status_indicator(avg_queue, 'queue_time')} |")
        md.append(f"| Average Execution Time | {avg_exec:.1f} minutes | {self._status_indicator(avg_exec, 'exec_time')} |")
        md.append(f"| Queue Impact | {queue_impact:.0f}% of total | {self._status_indicator(queue_impact, 'queue_impact')} |")
        md.append(f"| Runner Utilization | {util:.1f}% | {self._status_indicator(util, 'utilization')} |")
        md.append("")

        return "\n".join(md)

    def save_report(self, format='text'):
        """Save report to file."""
        if format == 'text':
            content = self.generate_text_report()
            extension = '.txt'
        elif format == 'markdown':
            content = self.generate_markdown_report()
            extension = '.md'
        else:
            raise ValueError(f"Unknown format: {format}")

        output_dir = Path('test_results/reports')
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"analysis_report_{timestamp}{extension}"
        filepath = output_dir / filename

        with open(filepath, 'w') as f:
            f.write(content)

        return filepath


def main():
    parser = argparse.ArgumentParser(description='Generate human-readable report from analysis')
    parser.add_argument('--format', choices=['text', 'markdown'], default='text',
                       help='Output format')
    parser.add_argument('--save', action='store_true',
                       help='Save report to file')
    parser.add_argument('--analysis-file',
                       help='Specific analysis file to use (default: most recent)')
    args = parser.parse_args()

    try:
        generator = ReportGenerator(args.analysis_file)

        if args.format == 'text':
            report = generator.generate_text_report()
        else:
            report = generator.generate_markdown_report()

        print(report)

        if args.save:
            filepath = generator.save_report(args.format)
            print(f"\n📄 Report saved to: {filepath}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run the analysis first: python analyze_test_results.py")


if __name__ == "__main__":
    main()
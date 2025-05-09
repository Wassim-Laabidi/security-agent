#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from config.settings import DEFAULT_ATTACK_GOALS
from agents.core_agent import CoreAgent
from workflows.attack_workflow import run_attack_workflow
from utils.context_manager import ContextManager

console = Console()

def print_banner():
    """Print the application banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   █████╗ ██╗   ██╗████████╗ ██████╗  █████╗ ████████╗████████╗ █████╗  ██████╗██╗  ██╗
    ║  ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗╚══██╔══╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝
    ║  ███████║██║   ██║   ██║   ██║   ██║███████║   ██║      ██║   ███████║██║     █████╔╝ 
    ║  ██╔══██║██║   ██║   ██║   ██║   ██║██╔══██║   ██║      ██║   ██╔══██║██║     ██╔═██╗ 
    ║  ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║  ██║   ██║      ██║   ██║  ██║╚██████╗██║  ██╗
    ║  ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
    ║                                                           ║
    ║             Autonomous Security Testing Agent            ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, border_style="red"))

def print_attack_goals():
    """Print available attack goals"""
    table = Table(title="Available Attack Goals")
    
    table.add_column("ID", style="dim")
    table.add_column("Goal Description", style="green")
    
    for i, goal in enumerate(DEFAULT_ATTACK_GOALS):
        table.add_row(str(i+1), goal)
    
    console.print(table)

def select_attack_goal() -> str:
    """Allow user to select an attack goal"""
    print_attack_goals()
    
    while True:
        try:
            choice = console.input("\n[bold]Select a goal by ID or enter a custom goal:[/bold] ")
            
            # Check if choice is a number
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(DEFAULT_ATTACK_GOALS):
                    return DEFAULT_ATTACK_GOALS[idx]
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            else:
                # Custom goal
                if len(choice.strip()) > 10:
                    return choice.strip()
                else:
                    console.print("[red]Custom goal must be at least 10 characters long.[/red]")
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

def run_attack_with_progress(goal: str, verbose: bool = False, max_steps: Optional[int] = None):
    """Run the attack workflow with a progress indicator"""
    context_manager = ContextManager()
    context_manager.set_attack_goal(goal)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[green]Running security test...", total=None)
        
        try:
            # Call run_attack_workflow with only the parameters it accepts
            results = run_attack_workflow(goal=goal)
            
            # After getting results, update the context manager
            for step in results['history']:
                context_manager.add_attack_step(step)
            for vulnerability in results['vulnerabilities']:
                context_manager.add_vulnerability(vulnerability)
            
            progress.update(task, completed=True, description="[green]Security test completed!")
            return results
        except Exception as e:
            progress.update(task, completed=True, description="[red]Security test failed!")
            console.print(f"[red]Error: {str(e)}[/red]")
            return None
# def run_attack_with_progress(goal: str, verbose: bool = False, max_steps: Optional[int] = None):
#     """Run the attack workflow with a progress indicator"""
#     context_manager = ContextManager()
#     context_manager.set_attack_goal(goal)
    
#     with Progress(
#         SpinnerColumn(),
#         TextColumn("[bold blue]{task.description}"),
#         transient=True,
#     ) as progress:
#         task = progress.add_task("[green]Running security test...", total=None)
        
#         try:
#             results = run_attack_workflow(
#                 goal=goal,
#                 context_manager=context_manager,
#                 verbose=verbose,
#                 max_steps=max_steps
#             )
            
#             progress.update(task, completed=True, description="[green]Security test completed!")
#             return results
#         except Exception as e:
#             progress.update(task, completed=True, description="[red]Security test failed!")
#             console.print(f"[red]Error: {str(e)}[/red]")
#             return None

def display_attack_results(results: Dict[str, Any]):
    """Display the attack results in a formatted manner"""
    if not results:
        console.print("[red]No results to display[/red]")
        return
    
    # Display attack summary
    console.print(Panel(f"[bold]Attack Goal:[/bold] {results.get('goal', 'N/A')}", title="Summary", border_style="blue"))
    
    # Display each attack step
    steps = results.get('steps', [])
    if not steps:
        console.print("[yellow]No attack steps were performed[/yellow]")
    else:
        for i, step in enumerate(steps):
            step_panel = Panel(
                f"[bold]Command:[/bold] {step.get('command', 'N/A')}\n\n"
                f"[bold]Output:[/bold]\n{step.get('output', 'N/A')[:500]}{'...' if len(step.get('output', '')) > 500 else ''}",
                title=f"Step {i+1}: {step.get('action', 'Action')}",
                border_style="green"
            )
            console.print(step_panel)
    
    # Display vulnerabilities found
    vulnerabilities = results.get('vulnerabilities', [])
    if vulnerabilities:
        vuln_table = Table(title="Vulnerabilities Found")
        vuln_table.add_column("Vulnerability", style="red")
        vuln_table.add_column("Severity", style="yellow")
        vuln_table.add_column("Remediation", style="green")
        
        for vuln in vulnerabilities:
            vuln_table.add_row(
                vuln.get('name', 'Unknown'),
                vuln.get('severity', 'Unknown'),
                vuln.get('remediation', 'No remediation suggested')
            )
        
        console.print(vuln_table)
    else:
        console.print("[green]No vulnerabilities were found[/green]")
    
    # Save results to file
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"results/attack_results_{timestamp}.json"
    
    os.makedirs("results", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    
    console.print(f"\n[blue]Results saved to: {filename}[/blue]")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AutoAttacker - Autonomous Security Testing Agent")
    parser.add_argument("--goal", "-g", type=str, help="Security testing goal")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--max-steps", "-m", type=int, default=None, help="Maximum number of attack steps")
    
    return parser.parse_args()

def main():
    """Main entry point for the application"""
    args = parse_arguments()
    
    print_banner()
    
    goal = args.goal
    if not goal:
        if args.interactive:
            goal = select_attack_goal()
        else:
            console.print("[red]Error: No goal specified. Use --goal or --interactive.[/red]")
            sys.exit(1)
    
    console.print(f"\n[bold]Starting security test with goal:[/bold] {goal}\n")
    
    results = run_attack_with_progress(
        goal=goal,
        verbose=args.verbose,
        max_steps=args.max_steps
    )
    
    if results:
        display_attack_results(results)

if __name__ == "__main__":
    main()
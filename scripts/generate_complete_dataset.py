#!/usr/bin/env python3
"""
Complete workflow for generating historical data with bundles.

This script orchestrates the full process:
1. Reset database
2. Generate orders, customers, drivers, stores
3. Bundle orders efficiently in batches
4. Show final statistics

Usage:
    python scripts/generate_complete_dataset.py --orders 100000 --days 60
    python scripts/generate_complete_dataset.py --orders 1200000 --days 60 --bundle-hours 6
    python scripts/generate_complete_dataset.py --orders 100000 --days 60 --deterministic --seed 42
    python scripts/generate_complete_dataset.py --orders 100000 --days 60 --deterministic --seed 42 --error-rate 0.05
"""

import argparse
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def run_command(cmd, description):
    """Run a command and track time."""
    print(f'\n{"="*80}')
    print(f'▶️  {description}')
    print(f'{"="*80}')
    
    start = datetime.now()
    
    result = subprocess.run(cmd, shell=True)
    
    elapsed = (datetime.now() - start).total_seconds()
    
    if result.returncode != 0:
        print(f'\n❌ Command failed with exit code {result.returncode}')
        sys.exit(1)
    
    print(f'\n✅ Completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)')
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description='Generate complete historical dataset with bundles'
    )
    parser.add_argument('--orders', type=int, default=100000,
                       help='Number of orders to generate (default: 100000)')
    parser.add_argument('--days', type=int, default=60,
                       help='Days of historical data (default: 60)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed (default: 42)')
    parser.add_argument('--bundle-hours', type=int, default=12,
                       help='Bundle batch size in hours (default: 12)')
    parser.add_argument('--skip-bundling', action='store_true',
                       help='Skip the bundling step')
    parser.add_argument('--bundle-limit-days', type=int,
                       help='Only bundle orders from recent N days')
    parser.add_argument('--deterministic', action='store_true',
                       help='Enable deterministic simulation mode (same seed = same output)')
    parser.add_argument('--error-rate', type=float, default=0.0,
                       help='Simulated error injection rate (0.0-1.0, default: 0.0)')
    parser.add_argument('--order-rate', type=float, default=6.0,
                       help='Order arrival rate per minute for Poisson process (default: 6.0)')
    
    args = parser.parse_args()
    
    print('='*80)
    print('COMPLETE HISTORICAL DATASET GENERATION')
    print('='*80)
    print(f'\n📊 Configuration:')
    print(f'   Orders:       {args.orders:,}')
    print(f'   Days:         {args.days}')
    print(f'   Seed:         {args.seed}')
    if not args.skip_bundling:
        print(f'   Bundle batch: {args.bundle_hours} hours')
        if args.bundle_limit_days:
            print(f'   Bundle limit: Last {args.bundle_limit_days} days only')
    if args.deterministic:
        print(f'   Mode:         DETERMINISTIC')
        if args.error_rate > 0:
            print(f'   Error rate:   {args.error_rate:.1%}')
        if args.order_rate != 6.0:
            print(f'   Order rate:   {args.order_rate}/min (Poisson)')
    
    total_start = datetime.now()
    
    # Step 1: Generate data
    gen_cmd = f'python main.py --reset --orders {args.orders} --days {args.days} --seed {args.seed}'
    if args.deterministic:
        gen_cmd += ' --deterministic'
    if args.error_rate > 0:
        gen_cmd += f' --error-rate {args.error_rate}'
    if args.order_rate != 6.0:
        gen_cmd += f' --order-rate {args.order_rate}'
    gen_time = run_command(gen_cmd, f'Step 1/2: Generating {args.orders:,} orders')
    
    # Step 2: Bundle orders (unless skipped)
    if not args.skip_bundling:
        bundle_cmd = f'python scripts/bundle_historical_orders.py --batch-hours {args.bundle_hours}'
        if args.bundle_limit_days:
            bundle_cmd += f' --limit-days {args.bundle_limit_days}'
        
        bundle_time = run_command(bundle_cmd, 'Step 2/2: Creating bundles')
    else:
        print(f'\n⏭️  Skipping bundling step')
        bundle_time = 0
    
    total_elapsed = (datetime.now() - total_start).total_seconds()
    
    # Final summary
    print('\n' + '='*80)
    print('🎉 DATASET GENERATION COMPLETE')
    print('='*80)
    print(f'\n⏱️  Time Breakdown:')
    print(f'   Order generation: {gen_time:.1f}s ({gen_time/60:.1f} min)')
    if not args.skip_bundling:
        print(f'   Bundle creation:  {bundle_time:.1f}s ({bundle_time/60:.1f} min)')
    print(f'   {"─"*40}')
    print(f'   Total:           {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)')
    
    print(f'\n📁 Database: database/grocery_delivery.db')
    print(f'\n💡 Next steps:')
    print(f'   - View stats:        python main.py --stats')
    print(f'   - Export to CSV:     python main.py --export')
    print(f'   - Start API server:  uvicorn api.main:app --reload --port 8000')
    print(f'   - Verify geofencing: python scripts/verify_geofencing.py')
    print('='*80)


if __name__ == '__main__':
    main()

# Sample fleet import guide

## Required columns
Each fleet file needs reading_id, vehicle_id, recorded_at, miles, and fuel_gallons in that order. Dates need a time zone. Miles and fuel values cannot be negative.

## Duplicate readings
A repeated reading_id with the same values is counted as a duplicate. A repeated ID with different values is rejected. The original reading stays in the database.

## Failed imports
After a database outage, the worker retries queued imports. A failed import can be retried from the import details page. Fix rejected rows in a new CSV file and upload that file again.

## Retention
This sample policy keeps raw CSV files for 30 days. This is a practice policy; automatic deletion has not been enabled in these demo apps.

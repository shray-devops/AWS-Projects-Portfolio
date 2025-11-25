## Author: Shreyas Pandey using Windsurf
## Date: 28 Nov 2025

import boto3
import os

def lambda_handler(event, context):
    # Initialize AWS clients
    ec2 = boto3.client('ec2')
    sns = boto3.client('sns')
    
    # Get SNS Topic ARN from environment variable
    SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:554000694136:sub_to_lambda_cost_optimization')
    
    # Get all EBS snapshots
    response = ec2.describe_snapshots(OwnerIds=['self'])

    # Get all active EC2 instance IDs
    instances_response = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    active_instance_ids = set()

    for reservation in instances_response['Reservations']:
        for instance in reservation['Instances']:
            active_instance_ids.add(instance['InstanceId'])

    # List to store deletion messages
    deletion_messages = []

    # Iterate through each snapshot and delete if it's not attached to any volume or the volume is not attached to a running instance
    for snapshot in response['Snapshots']:
        snapshot_id = snapshot['SnapshotId']
        volume_id = snapshot.get('VolumeId')
        message = ""
        subject = "EBS Snapshot Deletion Notification"

        if not volume_id:
            # Delete the snapshot if it's not attached to any volume
            ec2.delete_snapshot(SnapshotId=snapshot_id)
            message = f"Deleted EBS snapshot {snapshot_id} as it was not attached to any volume."
            print(message)
            deletion_messages.append(message)
        else:
            # Check if the volume still exists
            try:
                volume_response = ec2.describe_volumes(VolumeIds=[volume_id])
                if not volume_response['Volumes'][0]['Attachments']:
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    message = f"Deleted EBS snapshot {snapshot_id} as it was taken from a volume not attached to any running instance."
                    print(message)
                    deletion_messages.append(message)
            except ec2.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                    # The volume associated with the snapshot is not found (it might have been deleted)
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    message = f"Deleted EBS snapshot {snapshot_id} as its associated volume was not found."
                    print(message)
                    deletion_messages.append(message)

    # Send SNS notification if any snapshots were deleted
    if deletion_messages:
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"Deleted {len(deletion_messages)} Orphaned EBS Snapshots",
                Message="\n".join(deletion_messages)
            )
            print(f"Sent SNS notification about {len(deletion_messages)} deleted snapshots")
        except Exception as e:
            print(f"Error sending SNS notification: {str(e)}")
            raise

    return {
        'statusCode': 200,
        'body': f"Processed {len(deletion_messages)} snapshots"
    }

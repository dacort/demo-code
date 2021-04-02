from aws_cdk import core as cdk, aws_s3 as s3


def get_or_create_bucket(
    stack: cdk.Stack, bucket_id: str, context_key: str = None
) -> s3.Bucket:
    if context_key is None or stack.node.try_get_context(context_key) is None:
        return s3.Bucket(
            stack,
            bucket_id,
        )
    else:
        bucket_name = stack.node.try_get_context(context_key)
        return s3.Bucket.from_bucket_name(stack, bucket_id, bucket_name)
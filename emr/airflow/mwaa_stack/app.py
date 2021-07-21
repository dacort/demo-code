#!/usr/bin/env python3
import os

from aws_cdk import core as cdk

from mwaa.mwaa_stack import MwaaStack


app = cdk.App()
MwaaStack(app, "MwaaStack")

app.synth()

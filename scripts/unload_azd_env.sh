#!/bin/sh

while IFS='=' read -r key value; do
    value=$(echo "$value" | sed 's/^"//' | sed 's/"$//')
    unset "$key"
done <<EOF
$(azd env get-values)
EOF

echo "Unloaded azd env variables from current environment."

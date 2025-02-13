# We uterate over all the files in the configs directory and validate them

for f in (ls configs/generated/)
    echo "Validating $f"
    poetry run arb --log-level INFO check --config-file configs/generated/$f --trade-size 1  && continue

    echo "Validation failed for $f"
    rm configs/generated/$f

end
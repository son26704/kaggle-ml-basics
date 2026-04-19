from pathlib import Path
import textwrap

import nbformat


NOTEBOOK_PATH = Path("ppg_dalia.ipynb")


CELL_21 = textwrap.dedent(
    """
    if len(model_df) >= 50 and HAS_TF:
        import gc

        def build_tinyml_mlp(input_dim: int, config: dict):
            reg = keras.regularizers.l2(float(config.get("l2", 0.0)))
            inputs = keras.Input(shape=(input_dim,), name="ppg_features")
            x = inputs
            for idx, units in enumerate(config["layers"], start=1):
                x = layers.Dense(
                    units,
                    activation="relu",
                    kernel_initializer="he_normal",
                    kernel_regularizer=reg,
                    name=f"dense_{idx}",
                )(x)
                dropout_rate = float(config.get("dropout", 0.0))
                if dropout_rate > 0.0:
                    x = layers.Dropout(dropout_rate, name=f"dropout_{idx}")(x)

            outputs = layers.Dense(1, activation="linear", name="hr_pred_norm")(x)
            model = keras.Model(inputs=inputs, outputs=outputs, name=config["name"])
            model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=float(config.get("lr", 1e-3))),
                loss=keras.losses.Huber(delta=float(config.get("huber_delta", 1.0))),
                metrics=[keras.metrics.MeanAbsoluteError(name="mae")],
            )
            return model

        def denorm_hr(y_norm: np.ndarray, mean: float, std: float) -> np.ndarray:
            return (np.asarray(y_norm, dtype=np.float32).reshape(-1) * std + mean).astype(np.float32)

        y_train_full_vec = y_train.reshape(-1).astype(np.float32)
        y_test_vec = y_test_tiny.reshape(-1).astype(np.float32)
        train_groups_all = groups_all[tr_idx]

        split_val = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=SEED + 11)
        fit_idx, val_idx = next(split_val.split(X_train_raw, y_train_full_vec, groups=train_groups_all))

        X_fit_raw, X_val_raw = X_train_raw[fit_idx], X_train_raw[val_idx]
        y_fit_vec, y_val_vec = y_train_full_vec[fit_idx], y_train_full_vec[val_idx]
        groups_fit, groups_val = train_groups_all[fit_idx], train_groups_all[val_idx]

        tiny_scaler = StandardScaler()
        X_fit = tiny_scaler.fit_transform(X_fit_raw).astype(np.float32)
        X_val = tiny_scaler.transform(X_val_raw).astype(np.float32)
        X_test = tiny_scaler.transform(X_test_raw).astype(np.float32)
        X_train = X_fit
        y_train_vec = y_fit_vec.copy()

        hr_mean = float(np.mean(y_fit_vec))
        hr_std = float(np.std(y_fit_vec) + 1e-6)

        y_fit_norm = ((y_fit_vec - hr_mean) / hr_std).astype(np.float32).reshape(-1, 1)
        y_val_norm = ((y_val_vec - hr_mean) / hr_std).astype(np.float32).reshape(-1, 1)
        y_test_norm = ((y_test_vec - hr_mean) / hr_std).astype(np.float32)

        print("TinyML split (group-aware):")
        print("  Fit :", X_fit.shape, "| subjects =", np.unique(groups_fit).tolist())
        print("  Val :", X_val.shape, "| subjects =", np.unique(groups_val).tolist())
        print("  Test:", X_test.shape, "| subjects =", np.unique(groups_all[te_idx]).tolist())

        candidate_configs = [
            {
                "name": "baseline_64_32",
                "layers": [64, 32],
                "dropout": 0.00,
                "l2": 0.0,
                "lr": 1.0e-3,
                "batch_size": 128,
                "huber_delta": 1.0,
            },
            {
                "name": "mlp_128_128_64_do015",
                "layers": [128, 128, 64],
                "dropout": 0.15,
                "l2": 1.0e-4,
                "lr": 1.0e-3,
                "batch_size": 128,
                "huber_delta": 1.0,
            },
            {
                "name": "mlp_192_128_64_do020",
                "layers": [192, 128, 64],
                "dropout": 0.20,
                "l2": 1.0e-4,
                "lr": 8.0e-4,
                "batch_size": 128,
                "huber_delta": 1.0,
            },
            {
                "name": "mlp_256_128_64_do025",
                "layers": [256, 128, 64],
                "dropout": 0.25,
                "l2": 2.0e-4,
                "lr": 7.0e-4,
                "batch_size": 128,
                "huber_delta": 1.0,
            },
            {
                "name": "mlp_128_128_64_32_do020",
                "layers": [128, 128, 64, 32],
                "dropout": 0.20,
                "l2": 1.0e-4,
                "lr": 8.0e-4,
                "batch_size": 128,
                "huber_delta": 1.0,
            },
        ]

        candidate_results = []
        best_bundle = None

        def run_candidate(config: dict, iteration: int):
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(SEED + iteration)

            model = build_tinyml_mlp(X_fit.shape[1], config)
            callbacks = [
                keras.callbacks.EarlyStopping(
                    monitor="val_mae",
                    patience=25,
                    mode="min",
                    restore_best_weights=True,
                    verbose=0,
                ),
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_mae",
                    factor=0.5,
                    patience=8,
                    min_lr=1.0e-5,
                    verbose=0,
                ),
            ]

            history = model.fit(
                X_fit,
                y_fit_norm,
                validation_data=(X_val, y_val_norm),
                epochs=250,
                batch_size=int(config.get("batch_size", 128)),
                verbose=0,
                callbacks=callbacks,
            )

            fit_pred = denorm_hr(model.predict(X_fit, verbose=0), hr_mean, hr_std)
            val_pred = denorm_hr(model.predict(X_val, verbose=0), hr_mean, hr_std)

            train_mae = float(mean_absolute_error(y_fit_vec, fit_pred))
            val_mae = float(mean_absolute_error(y_val_vec, val_pred))
            val_rmse = float(np.sqrt(mean_squared_error(y_val_vec, val_pred)))
            overfit_gap = float(val_mae - train_mae)
            epochs_run = int(len(history.history["loss"]))
            best_epoch = int(np.argmin(history.history["val_mae"]) + 1)
            params = int(model.count_params())
            selection_score = float(val_mae + max(0.0, overfit_gap - 1.0) * 0.25 + params / 1.0e7)

            result = {
                "iteration": iteration,
                "name": config["name"],
                "layers": "-".join(str(x) for x in config["layers"]),
                "dropout": float(config.get("dropout", 0.0)),
                "l2": float(config.get("l2", 0.0)),
                "lr": float(config.get("lr", 1.0e-3)),
                "params": params,
                "epochs_run": epochs_run,
                "best_epoch": best_epoch,
                "train_mae": train_mae,
                "val_mae": val_mae,
                "val_rmse": val_rmse,
                "overfit_gap": overfit_gap,
                "selection_score": selection_score,
            }

            print(
                f"Iteration {iteration}: {config['name']} | params={params} | "
                f"epochs={epochs_run} | train_mae={train_mae:.4f} | "
                f"val_mae={val_mae:.4f} | gap={overfit_gap:.4f}"
            )

            bundle = {
                "config": dict(config),
                "weights": model.get_weights(),
                "history": {k: list(v) for k, v in history.history.items()},
                "result": result,
            }

            del model
            gc.collect()
            return result, bundle

        iteration = 1
        for config in candidate_configs:
            result, bundle = run_candidate(config, iteration)
            candidate_results.append(result)
            if best_bundle is None or result["selection_score"] < best_bundle["result"]["selection_score"]:
                best_bundle = bundle
            iteration += 1

        if best_bundle["result"]["val_mae"] > 7.0:
            print("Validation MAE still above target. Launching stage-2 wider models...")
            stage2_configs = [
                {
                    "name": "stage2_256_192_96_do030",
                    "layers": [256, 192, 96],
                    "dropout": 0.30,
                    "l2": 2.0e-4,
                    "lr": 5.0e-4,
                    "batch_size": 96,
                    "huber_delta": 1.0,
                },
                {
                    "name": "stage2_192_192_128_64_do025",
                    "layers": [192, 192, 128, 64],
                    "dropout": 0.25,
                    "l2": 1.0e-4,
                    "lr": 6.0e-4,
                    "batch_size": 96,
                    "huber_delta": 1.0,
                },
            ]
            for config in stage2_configs:
                result, bundle = run_candidate(config, iteration)
                candidate_results.append(result)
                if result["selection_score"] < best_bundle["result"]["selection_score"]:
                    best_bundle = bundle
                iteration += 1

        tinyml_candidates_df = pd.DataFrame(candidate_results).sort_values(
            ["selection_score", "val_mae", "params"], ascending=[True, True, True]
        ).reset_index(drop=True)
        display(tinyml_candidates_df)

        best_config = best_bundle["config"]
        best_result = best_bundle["result"]
        tinyml_model = build_tinyml_mlp(X_fit.shape[1], best_config)
        tinyml_model.set_weights(best_bundle["weights"])
        tinyml_history = best_bundle["history"]

        keras_pred_norm = tinyml_model.predict(X_test, verbose=0).reshape(-1)
        keras_pred = denorm_hr(keras_pred_norm, hr_mean, hr_std)

        keras_mae = float(mean_absolute_error(y_test_vec, keras_pred))
        keras_rmse = float(np.sqrt(mean_squared_error(y_test_vec, keras_pred)))
        keras_r2 = float(r2_score(y_test_vec, keras_pred))

        print("=== Selected TinyML Keras MLP ===")
        print(best_config)
        print(
            f"Validation MAE={best_result['val_mae']:.4f} | "
            f"Test MAE={keras_mae:.4f}, RMSE={keras_rmse:.4f}, R2={keras_r2:.4f}"
        )

        hist_df = pd.DataFrame(tinyml_history)
        hist_df["epoch"] = np.arange(1, len(hist_df) + 1)
        hist_df["train_mae_bpm"] = hist_df["mae"] * hr_std
        hist_df["val_mae_bpm"] = hist_df["val_mae"] * hr_std
        tinyml_history_df = hist_df.copy()

        plt.figure(figsize=(10, 4))
        plt.subplot(1, 2, 1)
        plt.plot(hist_df["epoch"], hist_df["loss"], label="train")
        plt.plot(hist_df["epoch"], hist_df["val_loss"], label="val")
        plt.xlabel("Epoch")
        plt.ylabel("Huber loss")
        plt.title("TinyML learning curves")
        plt.grid(alpha=0.2)
        plt.legend()

        plt.subplot(1, 2, 2)
        plt.plot(hist_df["epoch"], hist_df["train_mae_bpm"], label="train")
        plt.plot(hist_df["epoch"], hist_df["val_mae_bpm"], label="val")
        plt.xlabel("Epoch")
        plt.ylabel("MAE (BPM)")
        plt.title("TinyML train vs val MAE")
        plt.grid(alpha=0.2)
        plt.legend()
        plt.tight_layout()
        plt.show()

        tinyml_model_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp.keras"
        tinyml_model.save(tinyml_model_path)

        converter_fp32 = tf.lite.TFLiteConverter.from_keras_model(tinyml_model)
        tflite_fp32 = converter_fp32.convert()
        tflite_fp32_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp_fp32.tflite"
        tflite_fp32_path.write_bytes(tflite_fp32)

        def representative_dataset():
            n_rep = min(512, len(X_fit))
            idx = np.linspace(0, len(X_fit) - 1, n_rep, dtype=int)
            for i in idx:
                yield [X_fit[i:i+1].astype(np.float32)]

        converter_int8 = tf.lite.TFLiteConverter.from_keras_model(tinyml_model)
        converter_int8.optimizations = [tf.lite.Optimize.DEFAULT]
        converter_int8.representative_dataset = representative_dataset
        converter_int8.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter_int8.inference_input_type = tf.int8
        converter_int8.inference_output_type = tf.int8
        tflite_int8 = converter_int8.convert()
        tflite_int8_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp_int8.tflite"
        tflite_int8_path.write_bytes(tflite_int8)

        target_norm_meta = {
            "hr_mean": hr_mean,
            "hr_std": hr_std,
            "best_config": best_config,
            "validation_mae": best_result["val_mae"],
            "test_mae": keras_mae,
        }

        with open(TINYML_ARTIFACT_DIR / "tinyml_feature_columns.json", "w", encoding="utf-8") as f:
            json.dump(tinyml_feature_cols, f, ensure_ascii=False, indent=2)

        with open(TINYML_ARTIFACT_DIR / "tinyml_scaler.pkl", "wb") as f:
            pickle.dump(tiny_scaler, f)

        with open(TINYML_ARTIFACT_DIR / "tinyml_target_norm.json", "w", encoding="utf-8") as f:
            json.dump(target_norm_meta, f, ensure_ascii=False, indent=2)

        tinyml_candidates_df.to_csv(TINYML_ARTIFACT_DIR / "tinyml_candidate_results.csv", index=False)
        tinyml_history_df.to_csv(TINYML_ARTIFACT_DIR / "tinyml_best_history.csv", index=False)

        print("Saved:", tinyml_model_path)
        print("Saved:", tflite_fp32_path, "| size(bytes)=", tflite_fp32_path.stat().st_size)
        print("Saved:", tflite_int8_path, "| size(bytes)=", tflite_int8_path.stat().st_size)
        print("Saved:", TINYML_ARTIFACT_DIR / "tinyml_candidate_results.csv")
        print("Saved:", TINYML_ARTIFACT_DIR / "tinyml_best_history.csv")
        print("Saved:", TINYML_ARTIFACT_DIR / "tinyml_target_norm.json")
    """
).strip()


CELL_22 = textwrap.dedent(
    """
    if len(model_df) >= 50 and HAS_TF:
        def tflite_predict_regression(model_path: Path, x_float: np.ndarray):
            interpreter = tf.lite.Interpreter(model_path=str(model_path))
            interpreter.allocate_tensors()

            in_detail = interpreter.get_input_details()[0]
            out_detail = interpreter.get_output_details()[0]

            in_idx = in_detail["index"]
            out_idx = out_detail["index"]

            in_dtype = in_detail["dtype"]
            out_dtype = out_detail["dtype"]

            in_scale, in_zero = in_detail.get("quantization", (0.0, 0))
            out_scale, out_zero = out_detail.get("quantization", (0.0, 0))

            preds = []
            for i in range(len(x_float)):
                x = x_float[i:i+1].astype(np.float32)
                if in_dtype == np.int8:
                    x_q = np.clip(np.round(x / in_scale + in_zero), -128, 127).astype(np.int8)
                    interpreter.set_tensor(in_idx, x_q)
                else:
                    interpreter.set_tensor(in_idx, x.astype(in_dtype))

                interpreter.invoke()
                y = interpreter.get_tensor(out_idx)

                if out_dtype == np.int8:
                    y = (y.astype(np.float32) - out_zero) * out_scale
                preds.append(float(y.reshape(-1)[0]))

            return np.asarray(preds, dtype=np.float32), {
                "input_dtype": str(in_dtype),
                "output_dtype": str(out_dtype),
                "in_quant": (float(in_scale), int(in_zero)),
                "out_quant": (float(out_scale), int(out_zero)),
            }

        pred_fp32_norm, info_fp32 = tflite_predict_regression(tflite_fp32_path, X_test)
        pred_int8_norm, info_int8 = tflite_predict_regression(tflite_int8_path, X_test)

        pred_fp32 = (pred_fp32_norm * hr_std + hr_mean).astype(np.float32)
        pred_int8 = (pred_int8_norm * hr_std + hr_mean).astype(np.float32)

        fp32_mae = float(mean_absolute_error(y_test_vec, pred_fp32))
        fp32_rmse = float(np.sqrt(mean_squared_error(y_test_vec, pred_fp32)))

        int8_mae = float(mean_absolute_error(y_test_vec, pred_int8))
        int8_rmse = float(np.sqrt(mean_squared_error(y_test_vec, pred_int8)))

        compare_tinyml = pd.DataFrame([
            {
                "model": "Keras_MLP",
                "val_mae": best_result["val_mae"],
                "test_mae": keras_mae,
                "test_rmse": keras_rmse,
            },
            {
                "model": "TFLite_FP32",
                "val_mae": np.nan,
                "test_mae": fp32_mae,
                "test_rmse": fp32_rmse,
            },
            {
                "model": "TFLite_INT8",
                "val_mae": np.nan,
                "test_mae": int8_mae,
                "test_rmse": int8_rmse,
            },
        ])

        print("=== TinyML model comparison (denorm HR) ===")
        display(compare_tinyml)

        print("FP32 IO info:", info_fp32)
        print("INT8 IO info:", info_int8)

        size_fp32 = tflite_fp32_path.stat().st_size
        size_int8 = tflite_int8_path.stat().st_size
        print(f"Size FP32: {size_fp32/1024:.2f} KB")
        print(f"Size INT8: {size_int8/1024:.2f} KB")
        print(f"Compression ratio FP32/INT8: {size_fp32/max(size_int8,1):.3f}")

        n_export = min(16, len(X_test))
        x_export = X_test[:n_export]
        y_export = y_test_vec[:n_export]

        in_scale, in_zero = info_int8["in_quant"]
        x_export_q = np.clip(np.round(x_export / in_scale + in_zero), -128, 127).astype(np.int8)

        np.save(TINYML_ARTIFACT_DIR / "tinyml_x_test_fp32.npy", x_export.astype(np.float32))
        np.save(TINYML_ARTIFACT_DIR / "tinyml_x_test_int8.npy", x_export_q)
        np.save(TINYML_ARTIFACT_DIR / "tinyml_y_test.npy", y_export.astype(np.float32))
        compare_tinyml.to_csv(TINYML_ARTIFACT_DIR / "tinyml_model_compare.csv", index=False)

        print("Saved test vectors (.npy) in:", TINYML_ARTIFACT_DIR.resolve())
        print("Saved:", TINYML_ARTIFACT_DIR / "tinyml_model_compare.csv")
    """
).strip()


CELL_24 = textwrap.dedent(
    """
    if len(model_df) >= 50 and HAS_TF:
        def write_c_array_files(tflite_path: Path, header_path: Path, source_path: Path, var_name: str):
            data = tflite_path.read_bytes()
            guard = header_path.name.replace(".", "_").upper()
            header_text = "\\n".join([
                f"#ifndef {guard}",
                f"#define {guard}",
                "",
                "#ifdef __cplusplus",
                'extern "C" {',
                "#endif",
                "",
                f"extern const unsigned char {var_name}[];",
                f"extern const unsigned int {var_name}_len;",
                "",
                "#ifdef __cplusplus",
                "}",
                "#endif",
                "",
                f"#endif  // {guard}",
                "",
            ])

            lines = []
            for start in range(0, len(data), 12):
                chunk = data[start:start + 12]
                lines.append("  " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")

            source_text = "\\n".join([
                f'#include "{header_path.name}"',
                "",
                f"const unsigned char {var_name}[] = {{",
                *lines,
                "};",
                "",
                f"const unsigned int {var_name}_len = {len(data)};",
                "",
            ])

            header_path.write_text(header_text, encoding="ascii", newline="\\n")
            source_path.write_text(source_text, encoding="ascii", newline="\\n")

        int8_header_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp_int8.h"
        int8_source_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp_int8.c"
        write_c_array_files(
            tflite_int8_path,
            int8_header_path,
            int8_source_path,
            "ppg_hr_mlp_int8_tflite",
        )

        tiny_scaler_export = {
            "feature_mean": tiny_scaler.mean_.tolist(),
            "feature_scale": tiny_scaler.scale_.tolist(),
            "target_mean": hr_mean,
            "target_std": hr_std,
        }
        with open(TINYML_ARTIFACT_DIR / "tinyml_scaler_export.json", "w", encoding="utf-8") as f:
            json.dump(tiny_scaler_export, f, ensure_ascii=False, indent=2)

        print("const float kScalerMean[16] = {", ", ".join([f"{x:.9f}f" for x in tiny_scaler.mean_]), "};")
        print("const float kScalerScale[16] = {", ", ".join([f"{x:.9f}f" for x in tiny_scaler.scale_]), "};")
        print(f"const float kHrMeanBpm = {hr_mean:.9f}f;")
        print(f"const float kHrStdBpm = {hr_std:.9f}f;")
        print("Saved:", int8_header_path)
        print("Saved:", int8_source_path)
        print("Saved:", TINYML_ARTIFACT_DIR / "tinyml_scaler_export.json")
    """
).strip()


def main() -> None:
    nb = nbformat.read(NOTEBOOK_PATH.open("r", encoding="utf-8"), as_version=4)
    nb.cells[21].source = CELL_21
    nb.cells[22].source = CELL_22
    nb.cells[24].source = CELL_24
    nbformat.write(nb, NOTEBOOK_PATH.open("w", encoding="utf-8"))
    print(f"Patched {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()

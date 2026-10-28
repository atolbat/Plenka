plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ru.plenka.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "ru.plenka.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 149
        versionName = "3.20"
    }

    signingConfigs {
        create("release") {
            /* 3.18: секреты больше не в git (аудит): путь/пароль — из окружения.
               Экспорт перед сборкой: PLENKA_KS_PATH/PLENKA_KS_ALIAS/PLENKA_KS_PASS.
               Без env — unsigned-сборка (подписывает apksigner отдельно) */
            storeFile = file(System.getenv("PLENKA_KS_PATH") ?: "../plenka.keystore")
            storePassword = System.getenv("PLENKA_KS_PASS")
            keyAlias = System.getenv("PLENKA_KS_ALIAS") ?: "plenka"
            keyPassword = System.getenv("PLENKA_KS_PASS")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = if (System.getenv("PLENKA_KS_PASS") != null) signingConfigs.getByName("release") else null
        }
        debug {
            applicationIdSuffix = ""
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // ноль зависимостей: kotlin-stdlib подтягивается плагином, org.json — в Android framework
}

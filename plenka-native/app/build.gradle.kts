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
        versionCode = 145
        versionName = "3.16"
    }

    signingConfigs {
        create("release") {
            storeFile = file("../plenka.keystore")
            storePassword = "plenka2020"
            keyAlias = "plenka"
            keyPassword = "plenka2020"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("release")
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

console.log("popup.js loaded");


document.addEventListener("DOMContentLoaded", function(){


/* ===========================================================
                    ELEMENTS
=========================================================== */


const popup = document.getElementById("tourPopup");


if(!popup){

    console.log("Popup not found");
    return;

}



const popupCard = document.querySelector(".tour-popup-card");

const overlay = document.querySelector(".tour-popup-overlay");

const closeButton = document.querySelector(".popup-close");



const popupImage = document.getElementById("popupImage");

const popupGallery = document.getElementById("popupGallery");



const popupCountry = document.getElementById("popupCountry");
const popupTitle = document.getElementById("popupTitle");
const popupHotel = document.getElementById("popupHotel");
const popupDescription = document.getElementById("popupDescription");



const popupDeparture = document.getElementById("popupDeparture");
const popupNights = document.getElementById("popupNights");
const popupFood = document.getElementById("popupFood");



const popupPrice = document.getElementById("popupPrice");



const prevButton = document.getElementById("popupPrev");

const nextButton = document.getElementById("popupNext");



const buttons = document.querySelectorAll(".open-popup");



console.log("Buttons:", buttons.length);





/* ===========================================================
                    VARIABLES
=========================================================== */


let galleryImages = [];

let currentImage = 0;





/* ===========================================================
                    OPEN POPUP
=========================================================== */


buttons.forEach(function(button){


    button.addEventListener("click",function(e){


        e.preventDefault();



        galleryImages = [];



        if(this.dataset.gallery){


            galleryImages = this.dataset.gallery
            .split("|")
            .filter(Boolean);


        }



        if(galleryImages.length === 0){


            galleryImages.push(
                this.dataset.image
            );


        }



        currentImage = 0;



        fillPopup(this);



        createGallery();



        showImage();



        popup.classList.add("active");



        document.body.style.overflow="hidden";



    });



});





/* ===========================================================
                    FILL DATA
=========================================================== */


function fillPopup(button){


    popupCountry.textContent =
        button.dataset.country || "";



    popupTitle.textContent =
        button.dataset.title || "";



    popupHotel.textContent =
        "★★★★★ " +
        (button.dataset.hotel || "");



    popupDescription.textContent =
        button.dataset.description || "";



    popupDeparture.textContent =
        button.dataset.departure || "";



    popupNights.textContent =
        button.dataset.nights || "";



    popupFood.textContent =
        button.dataset.food || "";



    popupPrice.textContent =
        button.dataset.price || "";



}







/* ===========================================================
                    CREATE GALLERY
=========================================================== */


function createGallery(){


    popupGallery.innerHTML="";



    galleryImages.forEach(function(src,index){



        const img = document.createElement("img");



        img.src = src;



        img.className =
            "popup-thumb";



        if(index === 0){

            img.classList.add("active");

        }




        img.addEventListener("click",function(){


            currentImage=index;


            showImage();



        });



        popupGallery.appendChild(img);



    });



}







/* ===========================================================
                    CHANGE IMAGE
=========================================================== */


function showImage(){


    if(!galleryImages.length){

        return;

    }



    popupImage.style.opacity="0";



    setTimeout(function(){


        popupImage.src =
            galleryImages[currentImage];



        popupImage.onload=function(){


            popupImage.style.opacity="1";


        };


    },150);




    document
    .querySelectorAll(".popup-thumb")
    .forEach(function(img,index){


        img.classList.toggle(
            "active",
            index === currentImage
        );


    });



}






/* ===========================================================
                    ARROWS
=========================================================== */


function nextImage(){


    currentImage++;



    if(currentImage >= galleryImages.length){


        currentImage=0;


    }



    showImage();



}




function prevImage(){


    currentImage--;



    if(currentImage < 0){


        currentImage =
        galleryImages.length - 1;


    }



    showImage();



}





if(nextButton){


    nextButton.addEventListener(
        "click",
        nextImage
    );


}




if(prevButton){


    prevButton.addEventListener(
        "click",
        prevImage
    );


}

/* ===========================================================
                    CLOSE
=========================================================== */

function closePopup(){


    popup.classList.remove("active");

    document.body.style.overflow="";


}




if(closeButton){


    closeButton.addEventListener(
        "click",
        closePopup
    );


}




if(overlay){


    overlay.addEventListener(
        "click",
        closePopup
    );


}




if(popupCard){


    popupCard.addEventListener(
        "click",
        function(e){

            e.stopPropagation();

        }
    );


}






/* ===========================================================
                    KEYBOARD
=========================================================== */


document.addEventListener(
"keydown",
function(e){



    if(!popup.classList.contains("active")){

        return;

    }



    if(e.key==="Escape"){


        closePopup();


    }



    if(e.key==="ArrowRight"){


        nextImage();


    }



    if(e.key==="ArrowLeft"){


        prevImage();


    }



});





console.log("Popup initialized");



});